"""Integration tests for actions on data prepared before ingestion.

testkit's prepared three-component data have the horizontals rotated (Z and
T at `fiji_region` and `solomon_islands`, Z, L, Q and T at `central_peru`)
and every pick of a site on every channel. Each phase is measured per
component.
"""

import uuid
from pathlib import Path

import pytest
from pandas import Timedelta
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from aimbat import actions
from aimbat.core import PickSelection, readiness
from aimbat.core._readiness import ReadinessKind
from aimbat.core._validity import Validity
from aimbat.io import DataType
from aimbat.models import AimbatPhase, AimbatSeismogram, AimbatStation, phase_component

_LABELS = ("fiji_region", "central_peru", "solomon_islands")


def _label(seismogram: AimbatSeismogram) -> str:
    return Path(seismogram.datasource.sourcename).parent.name


def _phases(engine: Engine, label: str, name: str) -> dict[str, uuid.UUID]:
    """Return the IDs of the phases of that name at the event, by component."""
    with Session(engine) as session:
        phases = session.exec(
            select(AimbatPhase).where(col(AimbatPhase.name) == name)
        ).all()
        return {
            p.component: p.id for p in phases if _label(p.event.seismograms[0]) == label
        }


def _channels(engine: Engine, phase_id: uuid.UUID) -> set[str]:
    with Session(engine) as session:
        phase = session.get_one(AimbatPhase, phase_id)
        return {r.seismogram.station.channel for r in phase.seismogram_parameters}


@pytest.fixture
def prepared(
    patched_engine: Engine, three_component_data: dict[str, list[Path]]
) -> Engine:
    files = [p for label in _LABELS for p in three_component_data[f"prepared/{label}"]]
    result = actions.add_data(files, DataType.SAC, engine=patched_engine)
    assert result.snapshot_failures == []
    return patched_engine


class TestPhases:
    @pytest.mark.parametrize(
        ("label", "name", "components"),
        [
            ("fiji_region", "P", {"Z", "T"}),
            ("fiji_region", "S", {"Z", "T"}),
            ("solomon_islands", "S", {"Z", "T"}),
            ("central_peru", "SKS", {"Z", "L", "Q", "T"}),
        ],
    )
    def test_one_phase_per_component(
        self, prepared: Engine, label: str, name: str, components: set[str]
    ) -> None:
        assert set(_phases(prepared, label, name)) == components

    @pytest.mark.parametrize(
        ("label", "name", "component", "channels"),
        [
            ("fiji_region", "P", "Z", {"BHZ", "LHZ"}),
            ("fiji_region", "pP", "Z", {"BHZ", "LHZ"}),
            ("fiji_region", "S", "T", {"BHT", "LHT"}),
            ("solomon_islands", "S", "T", {"BHT"}),
            ("central_peru", "SKS", "Q", {"BHQ"}),
        ],
    )
    def test_rows_on_the_phase_component(
        self,
        prepared: Engine,
        label: str,
        name: str,
        component: str,
        channels: set[str],
    ) -> None:
        phase_id = _phases(prepared, label, name)[component]
        assert _channels(prepared, phase_id) == channels

    def test_every_row_has_its_phase_component(self, prepared: Engine) -> None:
        with Session(prepared) as session:
            for phase in session.exec(select(AimbatPhase)).all():
                for row in phase.seismogram_parameters:
                    assert phase_component(row.seismogram.station) == phase.component

    @pytest.mark.parametrize(
        ("kind", "sites"),
        [
            (ReadinessKind.DUPLICATE_SENSOR_STREAMS, {("AK", "PAX")}),
            (
                ReadinessKind.MULTIPLE_SENSORS_PER_SITE,
                {("IU", "COLA"), ("TA", "TOLK")},
            ),
            (ReadinessKind.MIXED_SAMPLING_RATES, {("AK", "PAX")}),
        ],
    )
    def test_sites_reported(
        self, prepared: Engine, kind: ReadinessKind, sites: set[tuple[str, str]]
    ) -> None:
        """PAX has BH and LH of one sensor, COLA and TOLK two sensors."""
        with Session(prepared) as session:
            items = [i for i in readiness(session) if i.kind is kind]
        assert items
        assert {site for i in items for site in i.sites} == sites

    def test_only_these_kinds(self, prepared: Engine) -> None:
        with Session(prepared) as session:
            kinds = {i.kind for i in readiness(session)}
        assert kinds == {
            ReadinessKind.DUPLICATE_SENSOR_STREAMS,
            ReadinessKind.MULTIPLE_SENSORS_PER_SITE,
            ReadinessKind.MIXED_SAMPLING_RATES,
        }

    def test_removing_one_stream_unblocks(self, prepared: Engine) -> None:
        _remove_long_period(prepared)
        with Session(prepared) as session:
            items = readiness(session)
        assert not any(i.blocking for i in items)


def _remove_long_period(engine: Engine) -> None:
    """Remove the picks of the PAX LH streams, which repeat its BH streams."""
    with Session(engine) as session:
        station_ids = session.exec(
            select(AimbatStation.id)
            .where(col(AimbatStation.name) == "PAX")
            .where(col(AimbatStation.channel).startswith("LH"))
        ).all()
    assert station_ids
    actions.remove_picks(PickSelection(station_ids=tuple(station_ids)), engine=engine)


class TestProcessing:
    """ICCS and MCCC on the component each phase is measured on."""

    def _align(
        self, engine: Engine, phase_id: uuid.UUID, limit: Timedelta
    ) -> dict[str, list[Timedelta]]:
        """Run ICCS and MCCC; return the residuals by site."""
        actions.run_iccs(phase_id, autoflip=True, autoselect=True)
        actions.run_mccc(phase_id)
        residuals: dict[str, list[Timedelta]] = {}
        with Session(engine) as session:
            assert Validity.read(session, phase_id).mccc(phase_id)
            phase = session.get_one(AimbatPhase, phase_id)
            for row in phase.seismogram_parameters:
                station = row.seismogram.station
                stream = f"{station.network}.{station.name}.{station.channel}"
                assert row.refined_pick is not None, stream
                residual = row.refined_pick - row.initial_pick
                assert abs(residual) < limit, stream
                site = f"{station.network}.{station.name}"
                residuals.setdefault(site, []).append(residual)
        return residuals

    def _sites_agree(self, residuals: dict[str, list[Timedelta]]) -> set[str]:
        """Check that channels of one site agree; return the sites with several."""
        shared = {site: r for site, r in residuals.items() if len(r) > 1}
        for site, (first, *others) in shared.items():
            for other in others:
                assert abs(other - first) < Timedelta(seconds=0.25), site
        return set(shared)

    def test_s_on_transverse(self, prepared: Engine) -> None:
        _remove_long_period(prepared)
        residuals = self._align(
            prepared, _phases(prepared, "fiji_region", "S")["T"], Timedelta(seconds=4)
        )
        assert self._sites_agree(residuals) == {"IU.COLA", "TA.TOLK"}

    def test_sks_on_q(self, prepared: Engine) -> None:
        residuals = self._align(
            prepared,
            _phases(prepared, "central_peru", "SKS")["Q"],
            Timedelta(seconds=2),
        )
        assert len(residuals) == 9

    def test_sks_on_t_apart_from_q(self, prepared: Engine) -> None:
        """T is aligned on its own, and Q keeps no result of it."""
        phases = _phases(prepared, "central_peru", "SKS")
        actions.run_iccs(phases["T"], autoflip=True, autoselect=True)
        actions.run_mccc(phases["T"])
        with Session(prepared) as session:
            assert Validity.read(session, phases["T"]).mccc(phases["T"])
            transverse = session.get_one(AimbatPhase, phases["T"])
            assert {
                r.seismogram.station.channel for r in transverse.seismogram_parameters
            } == {"BHT"}
            radial = session.get_one(AimbatPhase, phases["Q"])
            assert all(r.refined_pick is None for r in radial.seismogram_parameters)

    def test_p_on_z(self, prepared: Engine) -> None:
        _remove_long_period(prepared)
        residuals = self._align(
            prepared, _phases(prepared, "fiji_region", "P")["Z"], Timedelta(seconds=2)
        )
        assert self._sites_agree(residuals) == {"IU.COLA", "TA.TOLK"}
