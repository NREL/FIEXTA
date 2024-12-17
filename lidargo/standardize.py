import os
import xarray as xr
import numpy as np
import pandas as pd
import re
from scipy.optimize import curve_fit
from typing import Union, Optional
from dataclasses import asdict

from lidargo import utilities
from lidargo.utilities import get_logger, with_logging
from lidargo import vis
from lidargo.statistics import local_probability
from lidargo.config import LidarConfig


pd.set_option("future.no_silent_downcasting", True)


class Standardize:
    def __init__(
        self,
        source: str,
        config: Union[str, dict, LidarConfig],
        verbose: bool = True,
        logger: Optional[object] = None,
    ):
        """
        Initialize the LIDAR data processor with configuration parameters.

        Args:
            source (str): The input-level file name
            config (str, dict, or LidarConfig): Either a path to an Excel config file, a dictionary of configuration parameters, or a LidarConfig object
            verbose (bool, optional): Whether to print QC-related information. Defaults to True.
            logger (Logger, optional): Logger instance for logging messages. Defaults to None.
        """
        self.logger = get_logger(verbose=verbose, logger=logger)
        self.source = source

        self.logger.log(
            f"Initializing standardization of {os.path.basename(self.source)}"
        )

        # Load configuration based on input type
        self.config = self._load_configuration(config)
        if self.config is None:
            return

        # Load input data
        try:
            self.inputData = xr.open_dataset(self.source)
        except Exception as e:
            self.logger.log(f"Error loading input data: {str(e)}")
            return

    @with_logging
    def _load_configuration(
        self, config: Union[str, dict, LidarConfig]
    ) -> Optional[LidarConfig]:
        """
        Load configuration from either a file path, dictionary, or LidarConfig object.

        Args:
            config (str, dict, or LidarConfig): Configuration source

        Returns:
            LidarConfig or None: Configuration parameters or None if loading fails
        """
        try:
            if isinstance(config, LidarConfig):
                return config
            elif isinstance(config, str):
                return self._load_config_from_file(config)
            elif isinstance(config, dict):
                return LidarConfig(**config)
            else:
                self.logger.log(
                    f"Invalid config type. Expected str, dict, or LidarConfig, got {type(config)}"
                )
                return None
        except Exception as e:
            self.logger.log(f"Error loading configuration: {str(e)}")
            return None

    @with_logging
    def _load_config_from_file(self, config_file: str) -> Optional[LidarConfig]:
        """
        Load configuration from an Excel file.

        Args:
            config_file (str): Path to Excel configuration file

        Returns:
            LidarConfig or None: Configuration parameters or None if loading fails
        """
        configs = pd.read_excel(config_file).set_index("PARAMETER")
        date_source = np.int64(re.search(r"\d{8}.\d{6}", self.source).group(0)[:8])

        matches = []
        for regex in configs.columns:
            match = re.findall(regex, self.source)
            sdate = configs[regex]["start_date"]
            edate = configs[regex]["end_date"]
            if len(match) > 0 and sdate <= date_source <= edate:
                matches.append(regex)

        if not matches:
            self.logger.log("No regular expression matching the file name")
            return None
        elif len(matches) > 1:
            self.logger.log("Multiple regular expressions matching the file name")
            return None

        config_dict = configs[matches[0]].to_dict()
        try:
            return LidarConfig(**config_dict)
        except Exception as e:
            self.logger.log(f"Error validating configuration: {str(e)}")
            return None

    @with_logging
    def check_data(self):
        """
        Check input data for consistency
        """

        # Check distance (range) array.
        if "range_gate" in self.inputData.coords:
            if "overlapping" in self.inputData.attrs["Scan type"]:
                distance = np.unique(self.inputData["distance_overlapped"])
            else:
                distance = np.unique(self.inputData["distance"])
            distance = distance[~np.isnan(distance)]
            if len(distance) == 0:
                self.logger.log(
                    f"WARNING: All distance values are invalid on {os.path.basename(self.source)}, skipping it"
                )
                return False

        # Check for valid radial wind speed values
        if (
            self.inputData["wind_speed"].isnull().sum()
            == self.inputData["wind_speed"].size
        ):
            # All wind speeds are NaNs. Skipping
            self.logger.log(
                f"WARNING: All wind speeds are invalid on {os.path.basename(self.source)}, skipping it"
            )
            return False

        # Check for valid azimuth angles
        if self.inputData["azimuth"].isnull().sum() == self.inputData["azimuth"].size:
            # All azimuths are NaNs. Skipping
            self.logger.log(
                f"WARNING: All azimuths are invalid on {os.path.basename(self.source)}, skipping it"
            )
            return False

        # Check for valid elevation angles
        if (
            self.inputData["elevation"].isnull().sum()
            == self.inputData["elevation"].size
        ):
            # All azimuths are NaNs. Skipping
            self.logger.log(
                f"WARNING: All elevations are invalid on {os.path.basename(self.source)}, skipping it"
            )
            return False

        return True

    @with_logging
    def process_scan(
        self, make_figures=True, save_file=True, save_path=None, replace=True
    ):
        """
        Run all the processing.

        Inputs:
        -------
        make_figures: bool
            Whether or not generate QC figures
        save_file: bool
            Whether or not save the final processed file
        save_path: str
            String with the directory the destination of the processed files.
            Optional, defaults to analogous input, replacing input-level with output-level
            data. Creates the necessary intermediate directories
        replace: bool
            Whether or not to replace processed scan if one already exists
        """

        # Check if file has been processed yet and whether is to be replaced
        if "config" not in dir(self):
            self.logger.log(
                f"No configuration available. Skipping file {os.path.basename(self.source)}"
            )
            return

        # Compose filename
        save_filename = (
            ("." + self.config.data_level_out + ".")
            .join(self.source.split("." + self.config.data_level_in + "."))
            .replace(".nc", "." + self.config.project + "." + self.config.name + ".nc")
        )
        if save_path is not None:
            save_filename = os.path.join(save_path, os.path.basename(save_filename))

        self.save_filename = save_filename

        if os.path.exists(os.path.dirname(save_filename)) == False:
            os.makedirs(os.path.dirname(save_filename))

        if save_file and not replace and os.path.isfile(save_filename):
            self.logger.log(
                f"Processed file {save_filename} already exists, skipping it"
            )
            return
        else:
            self.logger.log(
                f"Generating standardized file {os.path.basename(save_filename)}"
            )

        # Check data
        if not self.check_data():
            return

        # Filter pre-processing
        self.remove_back_swipe()
        self.bin_and_count_angles()
        self.update_angles_to_nominal()

        # Apply qc filter
        self.filter_scan_data()

        # Re-index scan
        self.calculate_repetition_number()
        self.calculate_beam_number()
        self.identify_scan_mode()
        self.reindex_scan()
        self.add_attributes()

        if make_figures:
            self.qc_report()

        if save_file:
            self.outputData.to_netcdf(save_filename)
            self.logger.log(f"Standardized file saved as {save_filename}")

    @with_logging
    def remove_back_swipe(self):
        """
        Reject fast scanning head repositioning, identified based on the azimuth and elevation step thresholds.

        """

        # Angular difference (forward difference)
        diff_azi_fw = self.inputData["azimuth"].diff(dim="time", label="lower")
        diff_azi_fw[diff_azi_fw > 180] = diff_azi_fw[diff_azi_fw > 180] - 360
        diff_azi_fw[diff_azi_fw < -180] = diff_azi_fw[diff_azi_fw < -180] + 360

        diff_ele_fw = self.inputData["elevation"].diff(dim="time", label="lower")
        diff_ele_fw[diff_ele_fw > 180] = diff_ele_fw[diff_ele_fw > 180] - 360
        diff_ele_fw[diff_ele_fw < -180] = diff_ele_fw[diff_ele_fw < -180] + 360

        forward_swipe_condition_fw = (
            (diff_azi_fw >= self.config.min_azi_step)
            * (diff_azi_fw <= self.config.max_azi_step)
            * (diff_ele_fw >= self.config.min_ele_step)
            * (diff_ele_fw <= self.config.max_ele_step)
        )

        # Angular difference (backward difference)
        diff_azi_bw = self.inputData["azimuth"].diff(dim="time", label="upper")
        diff_azi_bw[diff_azi_bw > 180] = diff_azi_bw[diff_azi_bw > 180] - 360
        diff_azi_bw[diff_azi_bw < -180] = diff_azi_bw[diff_azi_bw < -180] + 360

        diff_ele_bw = self.inputData["elevation"].diff(dim="time", label="upper")
        diff_ele_bw[diff_ele_bw > 180] = diff_ele_bw[diff_ele_bw > 180] - 360
        diff_ele_bw[diff_ele_bw < -180] = diff_ele_bw[diff_ele_bw < -180] + 360

        forward_swipe_condition_bw = (
            (diff_azi_bw >= self.config.min_azi_step)
            * (diff_azi_bw <= self.config.max_azi_step)
            * (diff_ele_bw >= self.config.min_ele_step)
            * (diff_ele_bw <= self.config.max_ele_step)
        )

        # Contatenate swipe conditions
        forward_swipe_condition = xr.concat(
            [
                forward_swipe_condition_fw[0],
                forward_swipe_condition_fw | forward_swipe_condition_bw,
                forward_swipe_condition_bw[-1],
            ],
            dim="time",
        )

        # Remove beams in the deceleration phase of the scanning head
        azi_sel = self.inputData["azimuth"].where(forward_swipe_condition)
        ele_sel = self.inputData["elevation"].where(forward_swipe_condition)
        first = (azi_sel - azi_sel[0]) ** 2 + (
            ele_sel - ele_sel[0]
        ) ** 2 < self.config.ang_tol**2
        first_forward = xr.concat(
            [first[0], (forward_swipe_condition + 0).diff(dim="time") == 1], dim="time"
        )
        forward_swipe_condition[(first_forward == True) * (first == False)] = False

        self.outputData = self.inputData.where(forward_swipe_condition)
        self.azimuth_selected = self.outputData["azimuth"].copy()
        self.elevation_selected = self.outputData["elevation"].copy()

        self.logger.log(
            f"Back-swipe removal: {np.round(np.sum(forward_swipe_condition).values/len(self.inputData.azimuth)*100,2)}% retained"
        )

    # @with_logging ## <------- no logging in this method
    def bin_and_count_angles(self):
        """
        Perform binning and counting of scan data to identify most probable angles.
        """
        from scipy import stats

        llimit_azi = (
            utilities.floor(self.outputData.azimuth.min(), self.config.ang_tol)
            - self.config.ang_tol / 2
        )
        ulimit_azi = (
            utilities.ceil(self.outputData.azimuth.max(), self.config.ang_tol)
            + self.config.ang_tol
        )
        azi_bins = np.arange(llimit_azi, ulimit_azi, self.config.ang_tol)

        llimit_ele = (
            utilities.floor(self.outputData.elevation.min(), self.config.ang_tol)
            - self.config.ang_tol / 2
        )
        ulimit_ele = (
            utilities.ceil(self.outputData.elevation.max(), self.config.ang_tol)
            + self.config.ang_tol
        )
        ele_bins = np.arange(llimit_ele, ulimit_ele, self.config.ang_tol)

        E, A = np.meshgrid(utilities.mid(ele_bins), utilities.mid(azi_bins))
        counts = stats.binned_statistic_2d(
            self.outputData.azimuth,
            self.outputData.elevation,
            None,
            "count",
            bins=[azi_bins, ele_bins],
        )[0]
        counts_condition = counts / counts.max() > self.config.count_threshold

        self.counts = counts[counts_condition]
        self.azimuth_detected = A[counts_condition]
        self.elevation_detected = E[counts_condition]

    @with_logging
    def update_angles_to_nominal(self):
        """
        Update azimuth values to the nearest nominal bin centers within the specified tolerance.

        """

        try:  # (
            #     self.outputData is not None
            #     and "azimuth" in self.outputData
            #     and "elevation" in self.outputData
            # ):
            azi = self.outputData["azimuth"].values
            azimuth_bin_centers = self.azimuth_detected
            ele = self.outputData["elevation"].values
            elevation_bin_centers = self.elevation_detected

            # Calculate the absolute difference between azimuth values and bin centers
            diff_ang = (
                np.abs(azi[:, None] - azimuth_bin_centers[None, :]) ** 2
                + np.abs(ele[:, None] - elevation_bin_centers[None, :]) ** 2
            ) ** 0.5
            mindiff = xr.DataArray(
                data=diff_ang.min(axis=1), coords={"time": self.outputData.time}
            )
            mindiff[mindiff > self.config.ang_tol] = np.nan
            minind = np.argmin(diff_ang, axis=1)

            self.outputData["azimuth"].values = azimuth_bin_centers[minind]
            self.outputData["elevation"].values = elevation_bin_centers[minind]

            self.outputData = self.outputData.where(~np.isnan(mindiff))
            self.azimuth_regularized = self.outputData["azimuth"].copy()
            self.elevation_regularized = self.outputData["elevation"].copy()

            self.logger.log(
                f"Relevant angles detection: {np.round(np.sum(~np.isnan(self.azimuth_regularized.values+self.elevation_regularized.values))/len(self.inputData.azimuth)*100,2)}% retained"
            )

        except ValueError as e:
            self.logger.log(
                f"Dataset is not initialized or does not contain angle values: {str(e)}",
                level="error",
            )
            raise

    def filter_scan_data(self):
        """
        QC lidar data

        """

        df = self.scan_to_dataframe()

        # Apply prefiltering
        filterdf1 = self.pre_filter(df)
        df_temp = df.where(filterdf1.sum(axis=1) == len(filterdf1.columns))

        # Apply dynamic filter
        filterdf2, rws_norm, snr_norm, probability = self.dynamic_filter(df_temp)

        # Save qc flags
        filterdf = pd.concat([filterdf1, filterdf2], axis=1)
        df["qc_wind_speed"] = 0
        self.qc_flag = {}
        ctr = 1
        for c in filterdf.columns:
            self.qc_flag[c] = ctr
            if np.sum(filterdf[c] == False) > 0:
                mask = ~filterdf[c] & (df["qc_wind_speed"] == 0)
                df.loc[mask, "qc_wind_speed"] = ctr
            ctr += 1

        # Reorganize output dataframe
        df["rws_norm"] = rws_norm
        df["snr_norm"] = snr_norm
        df["probability"] = probability
        df = df.drop(["deltaTime"], axis=1)
        df = df[~df.index.duplicated(keep="first")]
        df = df.set_index(["time", "range"])

        # Back to xarray
        ds = xr.Dataset.from_dataframe(df)

        # Drop range dimension from beam properties
        ds["azimuth"] = ds["azimuth"].sel(range=ds["range"][0]).drop("range")
        ds["elevation"] = ds["elevation"].sel(range=ds["range"][0]).drop("range")
        ds["pitch"] = ds["pitch"].sel(range=ds["range"][0]).drop("range")
        ds["roll"] = ds["roll"].sel(range=ds["range"][0]).drop("range")

        # Inherit attributes
        ds.attrs = self.outputData.attrs

        for v in self.outputData.var():
            if v in ds.var():
                ds[v].attrs = self.outputData[v].attrs

        # Save filtered data
        self.outputData = ds

    def scan_to_dataframe(self):
        """
        Make a pandas dataframe to simplify filtering

        """

        # Add SNR floor
        self.outputData["SNR"] = self.outputData["SNR"].fillna(self.config.snr_min - 1)

        # Add time in seconds from start of the scan
        tnum = (
            self.outputData["time"] - np.datetime64("1970-01-01T00:00:00")
        ) / np.timedelta64(1, "s")
        self.outputData["deltaTime"] = tnum - tnum.min()

        # Swap range index with physical range
        if "overlapping" in self.inputData.attrs["Scan type"]:
            distance = np.unique(self.outputData.distance_overlapped)
        else:
            distance = np.unique(self.outputData.distance)
        distance = distance[~np.isnan(distance)]
        self.outputData = self.outputData.rename({"range_gate": "range"})
        self.outputData = self.outputData.assign_coords({"range": distance})

        # Add 3D coordinates
        self.outputData["x"], self.outputData["y"], self.outputData["z"] = (
            utilities.lidar_xyz(
                self.outputData["range"],
                self.outputData["elevation"],
                self.outputData["azimuth"] + self.config.azimuth_offset,
            )
        )

        df = (
            self.outputData[
                [
                    "x",
                    "y",
                    "z",
                    "wind_speed",
                    "SNR",
                    "deltaTime",
                    "azimuth",
                    "elevation",
                    "pitch",
                    "roll",
                ]
            ]
            .to_dataframe()
            .dropna(how="any")
        )
        df = df.reset_index()

        return df

    @with_logging
    def pre_filter(self, df):
        """
        Pre-filter of lidar data based on location and static rws and snr limits

        Inputs:
        ------
        df: dataframe
            dataframe of lidar data

        Outputs:
        ------
        filterdf: dataframe
            dataframe of QC flags
        df['rws_norm']: array of floats
            normalized radial wind speed
        df['snr_norm']: array of floats
            normalized SNR
        df['probability']: arrays of floats
            probability of rws-SNR histogram
        """
        filterdf = pd.DataFrame()

        # Range limits
        filt = (df["range"] >= self.config.range_min) & (
            df["range"] <= self.config.range_max
        )
        self.logger.log(
            f"range_limit filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["range_limit"] = filt.values

        # Ground rejection
        filt = df["z"] > self.config.ground_level
        self.logger.log(
            f"ground_limit filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["ground_limit"] = filt.values

        # SNR limit
        filt = df["SNR"] >= self.config.snr_min
        self.logger.log(
            f"snr_limit filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["snr_limit"] = filt

        # Wind speed max limit
        filt = np.abs(df["wind_speed"]) <= self.config.rws_max
        self.logger.log(
            f"rws_max filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["rws_max"] = filt

        # Wind speed min limit
        df_temp = df.where(filterdf.sum(axis=1) < len(filterdf.columns))
        self.rws_min = self.detect_resonance(df_temp)

        filt = np.abs(df["wind_speed"]) >= self.rws_min
        self.logger.log(
            f"rws_min filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["rws_min"] = filt

        return filterdf

    def detect_resonance(self, df):
        """
        Detect presence of resonance of bad data around 0 (some lidars have outliers clusterees aroun 0 m/s instead of uniformly spread acorss the bandwidth)

        Inputs:
        -----
        df: dataframe
            Dataframe of current data (bad data only)

        Outputs
        -----
        rws_min: float
            Lower threshold to be applied to absolute value of RWS. Detection is based on Gaussian fitting of histogram.

        """

        # build histogram if RWS normalized by maximum value
        df["rws_bins"] = pd.cut(
            df["wind_speed"] / df["wind_speed"].max(),
            bins=np.linspace(-1, 1, self.config.N_resonance_bins),
        )
        groups = df.groupby(by="rws_bins", group_keys=False, observed=True)
        H = groups["wind_speed"].count()

        # Normalize histogram by subtracting min and dividing by value in 0 (makes it more Gaussian)
        H = (H - H.min()) / H.iloc[int(self.config.N_resonance_bins / 2 - 1)]

        # Single-parameter Gaussian fit
        H_x = np.array([x.mid for x in H.index])
        sigma = curve_fit(utilities.gaussian, H_x, H, p0=[0.1], bounds=[0, 1])[0][0]

        # Check Gaussiainity and possibly calculate rws_min
        rmse = np.nanmean((utilities.gaussian(H_x, sigma) - H) ** 2) ** 0.5
        if rmse <= self.config.max_resonance_rmse:
            rws_min = 2 * sigma * df["wind_speed"].max()
            self.logger.log("Detected resonance")
        else:
            rws_min = 0

        self.configrws_min = rws_min

        return rws_min

    @with_logging
    def dynamic_filter(self, df):
        """
        Dynamic filter of lidar data based on normalized rws and snr based on Beck and Kuhn, Remote Sensing, 2017

        Inputs:
        -----
        df: dataframe
            dataframe of lidar data

        Outputs:
        -----
        filterdf: dataframe
            dataframe of QC flags

        """
        filterdf = pd.DataFrame()

        # Group df by x, y, z, time bins
        df = utilities.defineLocalBins(df, self.config)
        groups = df.groupby(
            ["xbins", "ybins", "zbins", "timebins"], group_keys=False, observed=True
        )

        # Normalized wind speed and SNR data channels
        df["rws_norm"] = groups["wind_speed"].apply(lambda x: x - x.median())
        df["snr_norm"] = groups["SNR"].apply(lambda x: x - x.median())

        # Normalized wind speed limit
        filt = np.abs(df["rws_norm"]) <= self.config.rws_norm_limit
        self.logger.log(
            f"rws_norm_limit filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["rws_norm_limit"] = filt

        # Minimum population
        filt = groups["rws_norm"].count() >= self.config.local_population_min_limit
        temp = df.set_index(["xbins", "ybins", "zbins", "timebins"]).copy()
        temp["local_population_min_limit"] = filt
        filt = temp["local_population_min_limit"].reset_index(drop=True)
        self.logger.log(
            f"local_population_min_limit filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["local_population_min_limit"] = filt

        # Standard error on the median filter
        filt = groups["rws_norm"].apply(
            lambda x: ((np.pi / 2) ** 0.5 * x.std()) / x.count() ** 0.5
            <= self.config.rws_standard_error_limit
        )
        temp = df.set_index(["xbins", "ybins", "zbins", "timebins"]).copy()
        temp["rws_standard_error_limit"] = filt
        filt = temp["rws_standard_error_limit"].reset_index(drop=True)
        self.logger.log(
            f"rws_standard_error_limit filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["rws_standard_error_limit"] = filt

        filt = groups["snr_norm"].apply(
            lambda x: ((np.pi / 2) ** 0.5 * x.std()) / x.count() ** 0.5
            <= self.config.snr_standard_error_limit
        )
        temp = df.set_index(["xbins", "ybins", "zbins", "timebins"]).copy()
        temp["snr_standard_error_limit"] = filt
        filt = temp["snr_standard_error_limit"].reset_index(drop=True)
        self.logger.log(
            f"snr_standard_error_limit filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["snr_standard_error_limit"] = filt

        # Probability conditions (applies actual dynamic filter)
        df["filtered_temp"] = filterdf.sum(axis=1) == len(
            filterdf.columns
        )  # points retained in previous steps
        filt, df, rws_range, probability_threshold = local_probability(df, self.config)
        self.logger.log(
            f"probability_limit filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["probability_limit"] = filt
        self.qc_rws_range = rws_range
        self.qc_probability_threshold = probability_threshold

        # Local scattering filter (removes isolated points)
        df["filtered_temp"] = filterdf.sum(axis=1) == len(
            filterdf.columns
        )  # points retained in previous steps
        filt = groups["filtered_temp"].mean() > self.config.local_scattering_min_limit
        temp = df.set_index(["xbins", "ybins", "zbins", "timebins"]).copy()
        temp["local_scattering_min_limit"] = filt
        filt = temp["local_scattering_min_limit"].reset_index(drop=True)
        filt = filt.reset_index(drop=True)
        self.logger.log(
            f"local_scattering_min_limit filter: {np.round(filt.sum()/len(filt)*100,2)}% retained"
        )
        filterdf["local_scattering_min_limit"] = filt
        df = df.drop("filtered_temp", axis=1)

        filterdf = filterdf.replace(np.nan, False)
        filterdf = filterdf.astype(np.int8)
        self.logger.log(
            f"Retained {np.round(100*filterdf.all(axis=1).sum()/len(filterdf),2)}% of data after QC"
        )

        return filterdf, df["rws_norm"], df["snr_norm"], df["probability"]

    @with_logging
    def calculate_repetition_number(self):
        """
        Calculate the repetition number of the scan
        """
        azi = self.outputData.azimuth.values
        ele = self.outputData.elevation.values
        time = self.outputData.time.values

        # Find scans' start
        scan_start = time[(azi == azi[0]) * (ele == ele[0])]

        # remove short scans (idling beam)
        scan_duration = np.diff(np.append(scan_start, time[-1]))
        scanID = pd.Series(
            data=np.zeros(len(scan_start)) - 9999, index=scan_start
        ).rename_axis("time")
        duration_condition = pd.Series(
            data=scan_duration
            > np.timedelta64(int(self.config.min_scan_duration * 10**9), "ns"),
            index=scanID.index,
        )
        self.logger.log(
            f"Scan duration check: {np.round(100*duration_condition.sum()/len(duration_condition),2)}% retained"
        )

        scanID[duration_condition] = np.arange(np.sum(duration_condition))
        scan_start_time = pd.Series(data=scan_start, index=scanID.index).rename_axis(
            "time"
        )

        # add scanID to dataset
        self.outputData["scanID"] = scanID
        self.outputData["scanID"].values = self.outputData["scanID"].ffill(dim="time")
        self.outputData["scan_start_time"] = scan_start_time
        self.outputData["scan_start_time"].values = self.outputData[
            "scan_start_time"
        ].ffill(dim="time")
        self.outputData = self.outputData.where(self.outputData["scanID"] >= 0)

    def calculate_beam_number(self):
        """
        Calculate the beam number based on how long after each scan start an angular position occurs on average
        """
        self.outputData["deltaTime"] = (
            self.outputData.time - self.outputData.scan_start_time
        ) / np.timedelta64(1, "s")
        deltaTime_regularized = np.zeros(len(self.outputData.time)) + np.nan
        deltaTime_median = np.zeros(len(self.azimuth_detected))
        ctr = 0
        for a, e in zip(self.azimuth_detected, self.elevation_detected):
            sel = (self.outputData.azimuth.values == a) * (
                self.outputData.elevation.values == e
            )
            deltaTime_median[ctr] = np.nanmedian(self.outputData.deltaTime[sel])
            deltaTime_regularized[sel] = np.nanmedian(self.outputData.deltaTime[sel])
            ctr += 1

        sort_angles = np.argsort(deltaTime_median[~np.isnan(deltaTime_median)])
        beamID = np.zeros(len(deltaTime_regularized)) + np.nan
        beamID[~np.isnan(deltaTime_regularized)] = np.where(
            (deltaTime_regularized[:, None] - np.unique(deltaTime_regularized)[None, :])
            == 0
        )[1]

        self.azimuth_detected = self.azimuth_detected[~np.isnan(deltaTime_median)][
            sort_angles
        ]
        self.elevation_detected = self.elevation_detected[~np.isnan(deltaTime_median)][
            sort_angles
        ]
        self.counts = self.counts[~np.isnan(deltaTime_median)][sort_angles]
        self.outputData["beamID"] = xr.DataArray(
            data=beamID, coords={"time": self.outputData.time.values}
        )

    @with_logging
    def reindex_scan(self):
        """
        Reindex the dataset from [time, range] to [range, beamID, scanID].

        Keeps all the time information in the dataset.
        """
        try:  # self.outputData is not None:

            # Copy time information
            self.outputData["time_temp"] = xr.DataArray(
                self.outputData.time.values,
                coords={"time": self.outputData.time.values},
            )

            # Reindex
            self.outputData = self.outputData.where(
                ~np.isnan(self.outputData.beamID + self.outputData.scanID), drop=True
            )
            self.outputData = self.outputData.set_index(time=["beamID", "scanID"])
            self.outputData = self.outputData.drop_duplicates("time").unstack()

            # Finalize dataset
            self.outputData = self.outputData.rename_vars({"time_temp": "time"})
            self.outputData = self.outputData.drop_vars(
                ["scan_start_time", "deltaTime"]
            )

            self.outputData = utilities.dropDuplicatedCoords(self.outputData)

        except ValueError as e:
            self.logger.log(f"Dataset is not initialized: {str(e)}", level="error")
            raise

    def identify_scan_mode(self):
        """
        Identify the type of scan, which is useful for plotting
        """
        azi = self.outputData["azimuth"].values
        ele = self.outputData["elevation"].values

        azimuth_variation = np.abs(np.nanmax(np.tan(azi)) - np.nanmin(np.tan(azi)))
        elevation_variation = np.abs(np.nanmax(np.cos(ele)) - np.nanmin(np.cos(ele)))

        if (
            elevation_variation < self.config.ang_tol
            and azimuth_variation < self.config.ang_tol
        ):
            self.outputData.attrs["scan_mode"] = "Stare"
        elif (
            elevation_variation < self.config.ang_tol
            and azimuth_variation > self.config.ang_tol
        ):
            self.outputData.attrs["scan_mode"] = "PPI"
        elif (
            elevation_variation > self.config.ang_tol
            and azimuth_variation < self.config.ang_tol
        ):
            self.outputData.attrs["scan_mode"] = "RHI"
        else:
            self.outputData.attrs["scan_mode"] = "3D"

    def add_attributes(self):
        """add attributes to output data channels, coords, etc."""
        self.outputData = utilities.add_attributes(self.outputData)
        qcAttrDict = {
            "qc_flag": self.qc_flag,
            "processConfig": asdict(self.config),
            "data_level": self.config.data_level_out,
            "datastream": self.save_filename,
            "qc_probability_threshold": self.qc_probability_threshold,
            "qc_rws_range": [b.mid for b in self.qc_rws_range.index],
        }
        self.outputData = utilities.add_qc_attrs(self.outputData, qcAttrDict)

    @with_logging
    def qc_report(self, saveFigs: bool = False, filetype: str = "png"):
        """
        Make figures.
        #TODO should the qc report have more flexibility?
        """

        wsqc_fig, scanqc_fig, az_fig, azhist_fig = vis.qcReport(
            self.outputData, self.inputData, self.qc_rws_range
        )

        if saveFigs:
            wsqc_fig.savefig(
                self.save_filename.replace(".nc", ".probability." + filetype)
            )
            scanqc_fig.savefig(self.save_filename.replace(".nc", ".qcscan." + filetype))
            az_fig.savefig(self.save_filename.replace(".nc", ".azScatter." + filetype))
            azhist_fig.savefig(self.save_filename.replace(".nc", ".azHist." + filetype))


if __name__ == "__main__":
    """
    Test block
    """
    import lidargo as lg
    cd = os.path.dirname(__file__)

    source = "../data/lidargo/example1/sc1.lidar.z01.a0.20230830.064613.user4.nc"
    config_file = "../configs/lidargo/config_examples_stand.xlsx"
    
    config_stand=pd.read_excel(config_file).set_index('regex')
    
    #match standardized config
    date_source=np.int64(re.search(r'\d{8}.\d{6}',source).group(0)[:8])
    
    matches=[]
    for regex in config_stand.columns:
        match = re.findall(regex, source)
        sdate=config_stand[regex]['start_date']
        edate=config_stand[regex]['end_date']
        if len(match)>0 and date_source>=sdate and date_source<=edate:
            matches.append(regex)

    if len(matches)==1:
        config = lg.LidarConfig(**config_stand[matches[0]].to_dict())
    
        # Run processing
        lproc = lg.Standardize(source, config=config, verbose=True)
        lproc.process_scan(replace=True, save_file=True, make_figures=True)

