# import warnings
import os
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.dates as mdates

from lidargo import utilities

# Not sure we need this here
# matplotlib.rcParams["font.family"] = "serif"
# matplotlib.rcParams["mathtext.fontset"] = "cm"
# matplotlib.rcParams["font.size"] = 10


#### Danger Danger!! Not sure this is a good idea
# warnings.filterwarnings("ignore", message="Mean of empty slice")
# warnings.filterwarnings("ignore", message=".*pcolor.*")
# warnings.filterwarnings("ignore", message=".*encountered in log10.*")
# warnings.filterwarnings("ignore", message=".*converting a masked element to nan.*")


def probabilityFig(ds, qc_rws_range):

    fig_probability = plt.figure(figsize=(18, 8))
    prob_arange = np.arange(
        np.log10(ds.qc_wind_speed.attrs["min_probability_range"]) - 1,
        np.log10(ds.qc_wind_speed.attrs["max_probability_range"]) + 1,
    )
    ax1 = plt.subplot(1, 2, 1)
    sp = plt.scatter(
        ds.rws_norm,
        ds.snr_norm,
        s=3,
        c=np.log10(ds.probability),
        cmap="hot",
        vmin=prob_arange[0],
        vmax=prob_arange[-1],
    )
    plt.xlabel("Normalized radial wind speed [m s$^{-1}$]")
    plt.ylabel("Normalized SNR [dB]")
    plt.grid()
    plt.title(
        "QC of data at "
        + ds.attrs["location_id"]
        + " on "
        + utilities.datestr(np.nanmean(utilities.dt64_to_num(ds["time"])), "%Y-%m-%d")
        + "\n File: "
        + os.path.basename(ds.attrs["datastream"])
    )

    ax2 = plt.subplot(1, 2, 2)
    plt.semilogx(
        ds.probability.values.ravel(),
        ds.rws_norm.values.ravel(),
        ".k",
        alpha=0.01,
        label="All points",
    )
    plt.semilogx(
        [10**b.mid for b in qc_rws_range.index],
        qc_rws_range.values,
        ".b",
        markersize=10,
        label="Range",
    )
    plt.semilogx(
        [
            ds["qc_wind_speed"].attrs["qc_probability_threshold"],
            ds["qc_wind_speed"].attrs["qc_probability_threshold"],
        ],
        [
            -ds["qc_wind_speed"].attrs["rws_norm_limit"],
            ds["qc_wind_speed"].attrs["rws_norm_limit"],
        ],
        "--r",
        label="Threshold",
    )
    plt.xlabel("Probability")
    plt.ylabel("Normalized radial wind speed [m s$^{-1}$]")
    ax2.yaxis.set_label_position("right")
    plt.legend()
    plt.grid()

    fig_probability.subplots_adjust(left=0.1, right=0.9, wspace=0.3)
    cax = fig_probability.add_axes(
        [
            ax1.get_position().x0 + ax1.get_position().width + 0.01,
            ax1.get_position().y0,
            0.015,
            ax1.get_position().height,
        ]
    )
    cbar = plt.colorbar(sp, cax=cax, label="Probability")
    cbar.set_ticks(prob_arange)
    cbar.set_ticklabels([r"$10^{" + str(int(p)) + "}$" for p in prob_arange])

    N_plot = np.min(np.array([5, len(ds.scanID)]))
    i_plot = [int(i) for i in np.linspace(0, len(ds.scanID) - 1, N_plot)]


def stareFig(ds):
    if ds.attrs["scan_mode"] == "Stare":
        time = (ds.time - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
        fig_rws = plt.figure(figsize=(18, 9))
        ax = plt.subplot(2, 1, 1)
        pc = plt.pcolor(
            ds["time"],
            r,
            rws[:, 0, :],
            cmap="coolwarm",
            vmin=np.nanpercentile(rws_qc, 5) - 1,
            vmax=np.nanpercentile(rws_qc, 95) + 1,
        )
        plt.xlabel("Time (UTC)")
        plt.ylabel(r"Range [m]")
        date_fmt = mdates.DateFormatter("%H:%M:%S")
        plt.gca().xaxis.set_major_formatter(date_fmt)
        plt.grid()
        plt.title(
            "Radial wind speed at "
            + ds.inputData.attrs["location_id"]
            + " on "
            + utilities.datestr(np.nanmean(time), "%Y-%m-%d")
            + "\n File: "
            + os.path.basename(ds.source)
            + "\n"
            + utilities.datestr(np.nanmin(time), "%H:%M:%S")
            + " - "
            + utilities.datestr(np.nanmax(time), "%H:%M:%S")
        )

        cax = fig_rws.add_axes(
            [
                ax.get_position().x0 + ax.get_position().width + 0.01,
                ax.get_position().y0,
                0.015,
                ax.get_position().height,
            ]
        )
        cbar = plt.colorbar(
            pc, cax=cax, label="Raw radial \n" + r" wind speed [m s$^{-1}$]"
        )

        ax = plt.subplot(2, 1, 2)
        pc = plt.pcolor(
            ds["time"],
            r,
            rws_qc[:, 0, :],
            cmap="coolwarm",
            vmin=np.nanpercentile(rws_qc, 5) - 1,
            vmax=np.nanpercentile(rws_qc, 95) + 1,
        )
        plt.xlabel("Time (UTC)")
        plt.ylabel(r"Range [m]")
        date_fmt = mdates.DateFormatter("%H:%M:%S")
        plt.gca().xaxis.set_major_formatter(date_fmt)
        plt.grid()
        cax = fig_rws.add_axes(
            [
                ax.get_position().x0 + ax.get_position().width + 0.01,
                ax.get_position().y0,
                0.015,
                ax.get_position().height,
            ]
        )
        cbar = plt.colorbar(
            pc, cax=cax, label="Filtered radial \n" + r" wind speed [m s$^{-1}$]"
        )


def ppiFig(ds):
    # if ds.attrs["scan_mode"] == "PPI":
    fig_angles = plt.figure(figsize=(18, 10))
    plt.subplot(2, 1, 1)
    plt.plot(
        ds.inputData["time"],
        ds.inputData["azimuth"].values.ravel(),
        ".k",
        markersize=5,
        label="Raw azimuth",
    )
    plt.plot(
        ds.azimuth_selected.time,
        ds.azimuth_selected,
        ".r",
        markersize=5,
        label="Selected azimuth",
    )
    plt.plot(
        ds.azimuth_regularized.time,
        ds.azimuth_regularized,
        ".g",
        markersize=5,
        label="Regularized azimuth",
    )
    plt.xlabel("Time (UTC)")
    plt.ylabel(r"Azimuth [$^\circ$]")
    date_fmt = mdates.DateFormatter("%H:%M:%S")
    plt.gca().xaxis.set_major_formatter(date_fmt)
    plt.legend()
    plt.grid()
    plt.title(
        "Beam angles at "
        + ds.inputData.attrs["location_id"]
        + " on "
        + utilities.datestr(
            np.nanmean(utilities.dt64_to_num(ds.inputData["time"])),
            "%Y-%m-%d",
        )
        + "\n File: "
        + os.path.basename(ds.source)
    )

    plt.subplot(2, 1, 2)
    plt.bar(ds.azimuth_detected, ds.counts, color="k")
    plt.xlabel(r"Detected significant azimuth [$^\circ$]")
    plt.ylabel("Occurrence")
    plt.grid()


def rhiFig(ds):
    # if ds.attrs["scan_mode"] == "RHI":
    fig_angles = plt.figure(figsize=(18, 10))
    plt.subplot(2, 1, 1)
    plt.plot(
        ds.inputData["time"],
        ds.inputData["elevation"].values.ravel(),
        ".k",
        markersize=5,
        label="Raw elevation",
    )
    plt.plot(
        ds.elevation_selected.time,
        ds.elevation_selected,
        ".r",
        markersize=5,
        label="Selected elevation",
    )
    plt.plot(
        ds.elevation_regularized.time,
        ds.elevation_regularized,
        ".g",
        markersize=5,
        label="Regularized elevation",
    )
    plt.xlabel("Time (UTC)")
    plt.ylabel(r"Elevation [$^\circ$]")
    date_fmt = mdates.DateFormatter("%H:%M:%S")
    plt.gca().xaxis.set_major_formatter(date_fmt)
    plt.legend()
    plt.grid()
    plt.title(
        "Beam angles at "
        + ds.inputData.attrs["location_id"]
        + " on "
        + utilities.datestr(
            np.nanmean(utilities.dt64_to_num(ds.inputData["time"])),
            "%Y-%m-%d",
        )
        + "\n File: "
        + os.path.basename(ds.source)
    )

    plt.subplot(2, 1, 2)
    plt.bar(ds.elevation_detected, ds.counts, color="k")
    plt.xlabel(r"Detected significant elevation [$^\circ$]")
    plt.ylabel("Occurrence")
    plt.grid()


def volumetricScanFig(ds):
    # if ds.attrs["scan_mode"] == "3D":
    fig_angles = plt.figure(figsize=(18, 10))
    plt.subplot(4, 1, 1)
    plt.plot(
        ds.inputData["time"],
        ds.inputData["azimuth"].values.ravel(),
        ".k",
        markersize=5,
        label="Raw azimuth",
    )
    plt.plot(
        ds.azimuth_selected.time,
        ds.azimuth_selected,
        ".r",
        markersize=5,
        label="Selected azimuth",
    )
    plt.plot(
        ds.azimuth_regularized.time,
        ds.azimuth_regularized,
        ".g",
        markersize=5,
        label="Regularized azimuth",
    )
    plt.ylabel(r"Azimuth [$^\circ$]")
    date_fmt = mdates.DateFormatter("%H:%M:%S")
    plt.gca().xaxis.set_major_formatter(date_fmt)
    plt.legend()
    plt.grid()
    plt.title(
        "Beam angles at "
        + ds.inputData.attrs["location_id"]
        + " on "
        + utilities.datestr(
            np.nanmean(utilities.dt64_to_num(ds.inputData["time"])),
            "%Y-%m-%d",
        )
        + "\n File: "
        + os.path.basename(ds.source)
    )

    plt.subplot(4, 1, 2)
    plt.plot(
        ds.inputData["time"],
        ds.inputData["elevation"].values.ravel(),
        ".k",
        markersize=5,
        label="Raw elevation",
    )
    plt.plot(
        ds.elevation_selected.time,
        ds.elevation_selected,
        ".r",
        markersize=5,
        label="Selected elevation",
    )
    plt.plot(
        ds.elevation_regularized.time,
        ds.elevation_regularized,
        ".g",
        markersize=5,
        label="Regularized elevation",
    )
    plt.xlabel("Time (UTC)")
    plt.ylabel(r"Elevation [$^\circ$]")
    date_fmt = mdates.DateFormatter("%H:%M:%S")
    plt.gca().xaxis.set_major_formatter(date_fmt)
    plt.legend()
    plt.grid()

    ax = plt.subplot(2, 1, 2)
    plt.plot(ds.azimuth_detected, ds.elevation_detected, "--k")
    sc = plt.scatter(
        ds.azimuth_detected,
        ds.elevation_detected,
        c=ds.counts,
        cmap="hot",
    )
    plt.xlabel(r"Azimuth [$^\circ$]")
    plt.ylabel(r"Elevation [$^\circ$]")
    plt.grid()
    cax = fig_angles.add_axes(
        [
            ax.get_position().x0 + ax.get_position().width + 0.01,
            ax.get_position().y0,
            0.015,
            ax.get_position().height,
        ]
    )
    cbar = plt.colorbar(sc, cax=cax, label="Occurrence")
    ax.set_facecolor("lightgrey")


def plot_rws(self, plot_type="xy"):
    """
    Plot 2D radial wind speed (RWS) data in different projections.

    Parameters:
    -----------
    plot_type : str
        Type of plot projection to use: 'xy' for horizontal, 'xz' for vertical
    """
    fig_rws = plt.figure(figsize=(18, 8))
    ctr = 1

    for i in i_plot:
        time = (ds.time[:, i] - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(
            1, "s"
        )

        # Set axes based on plot type
        if plot_type == "xy":
            X2, Y2 = X, Y
            y_label = r"$y$ [m]"
            ylim = [np.min(ds.y), np.max(ds.y)]
        else:  # xz projection
            X2, Y2 = X, Z
            y_label = r"$z$ [m]"
            ylim = [np.min(ds.z), np.max(ds.z)]

        xlim = [np.min(ds.x), np.max(ds.x)]

        # Plot raw and QC'ed RWS
        for subplot_idx, (data, label) in enumerate(
            [(rws, "Raw"), (rws_qc, "Filtered")]
        ):
            ax = plt.subplot(2, N_plot, ctr + subplot_idx * N_plot)
            pc = plt.pcolor(
                X2,
                Y2,
                data[:, :, i],
                cmap="coolwarm",
                vmin=np.nanpercentile(rws_qc, 5) - 1,
                vmax=np.nanpercentile(rws_qc, 95) + 1,
            )

            if ctr == 1:
                plt.ylabel(y_label)
            else:
                ax.set_yticklabels([])

            if subplot_idx == 1:
                plt.xlabel(r"$x$ [m]")

            plt.grid()
            ax.set_box_aspect(np.diff(ylim) / np.diff(xlim))
            plt.xlim(xlim)
            plt.ylim(ylim)

            # Add title and colorbar
            if ctr == np.ceil(N_plot / 2) and subplot_idx == 0:
                self._add_main_title(time)
            elif subplot_idx == 0:
                self._add_time_title(time)

            if ctr == N_plot:
                self._add_colorbar(
                    fig_rws, ax, pc, f"{label} radial\n wind speed [m s$^{-1}$]"
                )

        ctr += 1

    return fig_rws


def plot_beam_angles(self):
    """Plot beam angles analysis including azimuth, elevation, and occurrence."""
    fig_angles = plt.figure(figsize=(18, 10))

    # Azimuth time series
    plt.subplot(4, 1, 1)
    self._plot_angle_timeseries("azimuth")
    plt.ylabel(r"Azimuth [$^\circ$]")
    self._add_main_title(self.inputData["time"])

    # Elevation time series
    plt.subplot(4, 1, 2)
    self._plot_angle_timeseries("elevation")
    plt.xlabel("Time (UTC)")
    plt.ylabel(r"Elevation [$^\circ$]")

    # Azimuth vs Elevation occurrence plot
    ax = plt.subplot(2, 1, 2)
    plt.plot(self.azimuth_detected, self.elevation_detected, "--k")
    sc = plt.scatter(
        self.azimuth_detected, self.elevation_detected, c=self.counts, cmap="hot"
    )
    plt.xlabel(r"Azimuth [$^\circ$]")
    plt.ylabel(r"Elevation [$^\circ$]")
    plt.grid()
    ax.set_facecolor("lightgrey")
    self._add_colorbar(fig_angles, ax, sc, "Occurrence")

    return fig_angles


def plot_3d_rws(self):
    """Plot 3D visualization of radial wind speed data."""
    fig_rws = plt.figure(figsize=(18, 9))
    ctr = 1

    for i in i_plot:
        time = (
            self.outputData.time[:, i] - np.datetime64("1970-01-01T00:00:00")
        ) / np.timedelta64(1, "s")
        x, y, z = [self.outputData[coord][:, :, i].values for coord in ["x", "y", "z"]]

        # Plot raw and QC'ed RWS in 3D
        for subplot_idx, (data, label) in enumerate(
            [(rws, "Raw"), (rws_qc, "Filtered")]
        ):
            f = data[:, :, i].values
            real = ~np.isnan(x + y + z + f)

            # Subsample if too many points
            skip = int(np.sum(real) / 10000) if np.sum(real) > 10000 else 1

            ax = plt.subplot(2, N_plot, ctr + subplot_idx * N_plot, projection="3d")
            sc = self._plot_3d_scatter(ax, x, y, z, f, real, skip)

            if ctr == np.ceil(N_plot / 2) and subplot_idx == 0:
                self._add_main_title(time)
            elif subplot_idx == 0:
                self._add_time_title(time)

            if ctr == N_plot:
                self._add_colorbar(
                    fig_rws,
                    ax,
                    sc,
                    f"{label} radial\n wind speed [m s$^{-1}$]",
                    position_adjust=0.035,
                )

        ctr += 1

    plt.subplots_adjust(
        left=0.05, bottom=0.1, right=0.9, top=0.9, wspace=0.4, hspace=0.25
    )
    return fig_rws


def _plot_angle_timeseries(self, angle_type):
    """Helper function to plot angle time series."""
    plt.plot(
        self.inputData["time"],
        self.inputData[angle_type].values.ravel(),
        ".k",
        markersize=5,
        label=f"Raw {angle_type}",
    )
    plt.plot(
        getattr(self, f"{angle_type}_selected").time,
        getattr(self, f"{angle_type}_selected"),
        ".r",
        markersize=5,
        label=f"Selected {angle_type}",
    )
    plt.plot(
        getattr(self, f"{angle_type}_regularized").time,
        getattr(self, f"{angle_type}_regularized"),
        ".g",
        markersize=5,
        label=f"Regularized {angle_type}",
    )
    date_fmt = mdates.DateFormatter("%H:%M:%S")
    plt.gca().xaxis.set_major_formatter(date_fmt)
    plt.legend()
    plt.grid()


def _plot_3d_scatter(self, ax, x, y, z, f, real, skip):
    """Helper function for 3D scatter plotting."""
    sc = ax.scatter(
        x[real][::skip],
        y[real][::skip],
        z[real][::skip],
        s=2,
        c=f[real][::skip],
        cmap="coolwarm",
        vmin=np.nanpercentile(rws_qc, 5) - 1,
        vmax=np.nanpercentile(rws_qc, 95) + 1,
    )

    xlim = [np.min(self.outputData.x), np.max(self.outputData.x)]
    ylim = [np.min(self.outputData.y), np.max(self.outputData.y)]
    zlim = [np.min(self.outputData.z), np.max(self.outputData.z)]

    if ctr == 1:
        ax.set_xlabel(r"$x$ [m]", labelpad=10)
        ax.set_ylabel(r"$y$ [m]")
        ax.set_zlabel(r"$z$ [m]")
    else:
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.set_zticklabels([])

    ax.set_box_aspect((np.diff(xlim)[0], np.diff(ylim)[0], np.diff(zlim)[0]))
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_zlim(zlim)
    return sc


def _add_colorbar(self, fig, ax, mappable, label, position_adjust=0.01):
    """Helper function to add colorbar."""
    cax = fig.add_axes(
        [
            ax.get_position().x0 + ax.get_position().width + position_adjust,
            ax.get_position().y0,
            0.015,
            ax.get_position().height,
        ]
    )
    return plt.colorbar(mappable, cax=cax, label=label)


def _add_main_title(self, time):
    """Helper function to add main title."""
    plt.title(
        f"Radial wind speed at {self.inputData.attrs['location_id']} on "
        f"{utilities.datestr(np.nanmean(time), '%Y-%m-%d')}\n"
        f"File: {os.path.basename(self.source)}\n"
        f"{utilities.datestr(np.nanmin(time), '%H:%M:%S')} - "
        f"{utilities.datestr(np.nanmax(time), '%H:%M:%S')}"
    )


def _add_time_title(self, time):
    """Helper function to add time-only title."""
    plt.title(
        f"{utilities.datestr(np.nanmin(time), '%H:%M:%S')} - "
        f"{utilities.datestr(np.nanmax(time), '%H:%M:%S')}"
    )


# def rwsfig(ds):
#     fig_rws = plt.figure(figsize=(18, 8))
#     ctr = 1
#     for i in i_plot:
#         time = (ds.time[:, i] - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(
#             1, "s"
#         )

#         # plot raw rws
#         ax = plt.subplot(2, N_plot, ctr)
#         pc = plt.pcolor(
#             X,
#             Y,
#             rws[:, :, i],
#             cmap="coolwarm",
#             vmin=np.nanpercentile(rws_qc, 5) - 1,
#             vmax=np.nanpercentile(rws_qc, 95) + 1,
#         )
#         if ctr == 1:
#             plt.ylabel(r"$y$ [m]")
#         else:
#             ax.set_yticklabels([])
#         plt.grid()

#         xlim = [np.min(ds.x), np.max(ds.x)]
#         ylim = [np.min(ds.y), np.max(ds.y)]
#         ax.set_box_aspect(np.diff(ylim) / np.diff(xlim))
#         plt.xlim(xlim)
#         plt.ylim(ylim)
#         plt.title(
#             utilities.datestr(np.nanmin(time), "%H:%M:%S")
#             + " - "
#             + utilities.datestr(np.nanmax(time), "%H:%M:%S")
#         )

#         if ctr == np.ceil(N_plot / 2):
#             plt.title(
#                 "Radial wind speed at "
#                 + ds.inputData.attrs["location_id"]
#                 + " on "
#                 + utilities.datestr(np.nanmean(time), "%Y-%m-%d")
#                 + "\n File: "
#                 + os.path.basename(ds.source)
#                 + "\n"
#                 + utilities.datestr(np.nanmin(time), "%H:%M:%S")
#                 + " - "
#                 + utilities.datestr(np.nanmax(time), "%H:%M:%S")
#             )

#         if ctr == N_plot:
#             cax = fig_rws.add_axes(
#                 [
#                     ax.get_position().x0 + ax.get_position().width + 0.01,
#                     ax.get_position().y0,
#                     0.015,
#                     ax.get_position().height,
#                 ]
#             )
#             cbar = plt.colorbar(
#                 pc, cax=cax, label="Raw radial \n" + r" wind speed [m s$^{-1}$]"
#             )

#         # plot qc'ed rws
#         ax = plt.subplot(2, N_plot, ctr + N_plot)
#         plt.pcolor(
#             X,
#             Y,
#             rws_qc[:, :, i],
#             cmap="coolwarm",
#             vmin=np.nanpercentile(rws_qc, 5) - 1,
#             vmax=np.nanpercentile(rws_qc, 95) + 1,
#         )
#         plt.xlabel(r"$x$ [m]")
#         if ctr == 1:
#             plt.ylabel(r"$y$ [m]")
#         else:
#             ax.set_yticklabels([])
#         xlim = [np.min(ds.x), np.max(ds.x)]
#         ylim = [np.min(ds.y), np.max(ds.y)]
#         ax.set_box_aspect(np.diff(ylim) / np.diff(xlim))
#         plt.xlim(xlim)
#         plt.ylim(ylim)
#         plt.grid()

#         if ctr == N_plot:
#             if ctr == N_plot:
#                 cax = fig_rws.add_axes(
#                     [
#                         ax.get_position().x0 + ax.get_position().width + 0.01,
#                         ax.get_position().y0,
#                         0.015,
#                         ax.get_position().height,
#                     ]
#                 )
#                 cbar = plt.colorbar(
#                     pc,
#                     cax=cax,
#                     label="Filtered radial \n" + r" wind speed [m s$^{-1}$]",
#                 )
#         ctr += 1


# def rwsFig2(ds):
#     fig_rws = plt.figure(figsize=(18, 8))
#     ctr = 1
#     for i in i_plot:
#         time = (ds.time[:, i] - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(
#             1, "s"
#         )

#         # plot raw rws
#         ax = plt.subplot(2, N_plot, ctr)
#         pc = plt.pcolor(
#             X,
#             Z,
#             rws[:, :, i],
#             cmap="coolwarm",
#             vmin=np.nanpercentile(rws_qc, 5) - 1,
#             vmax=np.nanpercentile(rws_qc, 95) + 1,
#         )
#         if ctr == 1:
#             plt.ylabel(r"$z$ [m]")
#         else:
#             ax.set_yticklabels([])
#         plt.grid()

#         xlim = [np.min(ds.x), np.max(ds.x)]
#         zlim = [np.min(ds.z), np.max(ds.z)]
#         ax.set_box_aspect(np.diff(zlim) / np.diff(xlim))
#         plt.xlim(xlim)
#         plt.ylim(zlim)
#         plt.title(
#             utilities.datestr(np.nanmin(time), "%H:%M:%S")
#             + " - "
#             + utilities.datestr(np.nanmax(time), "%H:%M:%S")
#         )

#         if ctr == np.ceil(N_plot / 2):
#             plt.title(
#                 "Radial wind speed at "
#                 + ds.inputData.attrs["location_id"]
#                 + " on "
#                 + utilities.datestr(np.nanmean(time), "%Y-%m-%d")
#                 + "\n File: "
#                 + os.path.basename(ds.source)
#                 + "\n"
#                 + utilities.datestr(np.nanmin(time), "%H:%M:%S")
#                 + " - "
#                 + utilities.datestr(np.nanmax(time), "%H:%M:%S")
#             )

#         if ctr == N_plot:
#             cax = fig_rws.add_axes(
#                 [
#                     ax.get_position().x0 + ax.get_position().width + 0.01,
#                     ax.get_position().y0,
#                     0.015,
#                     ax.get_position().height,
#                 ]
#             )
#             cbar = plt.colorbar(
#                 pc, cax=cax, label="Raw radial \n" + r" wind speed [m s$^{-1}$]"
#             )

#         # plot qc'ed rws
#         ax = plt.subplot(2, N_plot, ctr + N_plot)
#         plt.pcolor(
#             X,
#             Z,
#             rws_qc[:, :, i],
#             cmap="coolwarm",
#             vmin=np.nanpercentile(rws_qc, 5) - 1,
#             vmax=np.nanpercentile(rws_qc, 95) + 1,
#         )
#         plt.xlabel(r"$x$ [m]")
#         if ctr == 1:
#             plt.ylabel(r"$z$ [m]")
#         else:
#             ax.set_yticklabels([])

#         ax.set_box_aspect(np.diff(zlim) / np.diff(xlim))
#         plt.xlim(xlim)
#         plt.ylim(zlim)
#         plt.grid()

#         if ctr == N_plot:
#             if ctr == N_plot:
#                 cax = fig_rws.add_axes(
#                     [
#                         ax.get_position().x0 + ax.get_position().width + 0.01,
#                         ax.get_position().y0,
#                         0.015,
#                         ax.get_position().height,
#                     ]
#                 )
#                 cbar = plt.colorbar(
#                     pc,
#                     cax=cax,
#                     label="Filtered radial \n" + r" wind speed [m s$^{-1}$]",
#                 )
#         ctr += 1


# def rwsfig3(ds):
#     fig_rws = plt.figure(figsize=(18, 9))
#     ctr = 1
#     for i in i_plot:
#         time = (ds.time[:, i] - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(
#             1, "s"
#         )
#         x = ds.x[:, :, i].values
#         y = ds.y[:, :, i].values
#         z = ds.z[:, :, i].values
#         f = rws[:, :, i].values
#         real = ~np.isnan(x + y + z + f)

#         if np.sum(real) > 10000:
#             skip = int(np.sum(real) / 10000)
#         else:
#             skip = 1

#         # plot raw rws
#         xlim = [np.min(ds.x), np.max(ds.x)]
#         ylim = [np.min(ds.y), np.max(ds.y)]
#         zlim = [np.min(ds.z), np.max(ds.z)]

#         ax = plt.subplot(2, N_plot, ctr, projection="3d")
#         sc = ax.scatter(
#             x[real][::skip],
#             y[real][::skip],
#             z[real][::skip],
#             s=2,
#             c=f[real][::skip],
#             cmap="coolwarm",
#             vmin=np.nanpercentile(rws_qc, 5) - 1,
#             vmax=np.nanpercentile(rws_qc, 95) + 1,
#         )
#         if ctr == 1:
#             ax.set_xlabel(r"$x$ [m]", labelpad=10)
#             ax.set_ylabel(r"$y$ [m]")
#             ax.set_zlabel(r"$z$ [m]")
#         else:
#             ax.set_xticklabels([])
#             ax.set_yticklabels([])
#             ax.set_zticklabels([])

#         ax.set_box_aspect((np.diff(xlim)[0], np.diff(ylim)[0], np.diff(zlim)[0]))
#         ax.set_xlim(xlim)
#         ax.set_ylim(ylim)
#         ax.set_zlim(zlim)
#         plt.title(
#             utilities.datestr(np.nanmin(time), "%H:%M:%S")
#             + " - "
#             + utilities.datestr(np.nanmax(time), "%H:%M:%S")
#         )

#         if ctr == np.ceil(N_plot / 2):
#             plt.title(
#                 "Radial wind speed at "
#                 + ds.inputData.attrs["location_id"]
#                 + " on "
#                 + utilities.datestr(np.nanmean(time), "%Y-%m-%d")
#                 + "\n File: "
#                 + os.path.basename(ds.source)
#                 + "\n"
#                 + utilities.datestr(np.nanmin(time), "%H:%M:%S")
#                 + " - "
#                 + utilities.datestr(np.nanmax(time), "%H:%M:%S")
#             )

#         if ctr == N_plot:
#             cax = fig_rws.add_axes(
#                 [
#                     ax.get_position().x0 + ax.get_position().width + 0.035,
#                     ax.get_position().y0,
#                     0.015,
#                     ax.get_position().height,
#                 ]
#             )
#             cbar = plt.colorbar(
#                 sc, cax=cax, label="Raw radial \n" + r" wind speed [m s$^{-1}$]"
#             )

#         # plot qc'ed rws
#         f = rws_qc[:, :, i].values
#         real = ~np.isnan(x + y + z + f)
#         ax = plt.subplot(2, N_plot, ctr + N_plot, projection="3d")
#         sc = ax.scatter(
#             x[real],
#             y[real],
#             z[real],
#             s=2,
#             c=f[real],
#             cmap="coolwarm",
#             vmin=np.nanpercentile(rws_qc, 5) - 1,
#             vmax=np.nanpercentile(rws_qc, 95) + 1,
#         )

#         if ctr == 1:
#             ax.set_xlabel(r"$x$ [m]", labelpad=10)
#             ax.set_ylabel(r"$y$ [m]")
#             ax.set_zlabel(r"$z$ [m]")
#         else:
#             ax.set_xticklabels([])
#             ax.set_yticklabels([])
#             ax.set_zticklabels([])

#         ax.set_box_aspect((np.diff(xlim)[0], np.diff(ylim)[0], np.diff(zlim)[0]))
#         ax.set_xlim(xlim)
#         ax.set_ylim(ylim)
#         ax.set_zlim(zlim)
#         plt.grid()

#         if ctr == N_plot:
#             if ctr == N_plot:
#                 cax = fig_rws.add_axes(
#                     [
#                         ax.get_position().x0 + ax.get_position().width + 0.035,
#                         ax.get_position().y0,
#                         0.015,
#                         ax.get_position().height,
#                     ]
#                 )
#                 cbar = plt.colorbar(
#                     sc,
#                     cax=cax,
#                     label="Filtered radial \n" + r" wind speed [m s$^{-1}$]",
#                 )
#         ctr += 1
#         plt.subplots_adjust(
#             left=0.05, bottom=0.1, right=0.9, top=0.9, wspace=0.4, hspace=0.25
#         )
