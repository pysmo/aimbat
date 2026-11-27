"""Integration tests for actions on real three-component data.

testkit's three-component data are three events recorded on Z and both
horizontals. P (`t0`) and pP (`t5`) are picked on Z, S (`t6`) and SKS (`t7`)
on the horizontals. Some sites have two location codes, or channels at
different sampling rates.
"""

import re
import uuid
from pathlib import Path

import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from pysmo import Station
from pysmo.classes import SAC

from aimbat import actions
from aimbat.core import PickSelection
from aimbat.core._validity import Validity
from aimbat.io import DataType
from aimbat.models import AimbatEvent, AimbatPhase, AimbatSeismogram, AimbatStation

_EVENTS = ("fiji_region", "central_peru", "solomon_islands")
_HEADERS = {"P": "t0", "pP": "t5", "S": "t6", "SKS": "t7"}


def _stream(station: Station) -> str:
    return f"{station.network}.{station.name}.{station.location}.{station.channel}"


def _label(seismogram: AimbatSeismogram) -> str:
    """The testkit directory, and so the event label, of a seismogram's source."""
    return Path(seismogram.datasource.sourcename).parent.name


def _event_files(data: dict[str, list[Path]]) -> list[Path]:
    return [path for label in _EVENTS for path in data[label]]


@pytest.fixture
def imported(
    patched_engine: Engine, three_component_data: dict[str, list[Path]]
) -> Engine:
    result = actions.add_data(
        _event_files(three_component_data), DataType.SAC, engine=patched_engine
    )
    assert result.snapshot_failures == []
    return patched_engine


class TestImport:
    """Each channel becomes a seismogram, and each pick joins its phase."""

    def test_one_seismogram_per_file(
        self, imported: Engine, three_component_data: dict[str, list[Path]]
    ) -> None:
        expected: dict[tuple[str, str], Timedelta] = {}
        for path in _event_files(three_component_data):
            sac = SAC.from_file(path)
            expected[(path.parent.name, _stream(sac.station))] = sac.seismogram.delta

        with Session(imported) as session:
            seismograms = session.exec(select(AimbatSeismogram)).all()
            found = {
                (_label(seismogram), _stream(seismogram.station)): seismogram.delta
                for seismogram in seismograms
            }
        assert len(seismograms) == len(_event_files(three_component_data))
        assert found == expected

    def test_sites(
        self, imported: Engine, three_component_data: dict[str, list[Path]]
    ) -> None:
        with Session(imported) as session:
            found = {
                _label(event.seismograms[0]): (len(event.seismograms), event.site_count)
                for event in session.exec(select(AimbatEvent)).all()
            }
        expected = {
            label: (
                len(three_component_data[label]),
                len(
                    {
                        ".".join(p.name.split(".")[:2])
                        for p in three_component_data[label]
                    }
                ),
            )
            for label in _EVENTS
        }
        assert found == expected

    def test_phases_per_event(self, imported: Engine) -> None:
        with Session(imported) as session:
            found = {
                _label(event.seismograms[0]): {phase.name for phase in event.phases}
                for event in session.exec(select(AimbatEvent)).all()
            }
        assert found == {
            "fiji_region": {"P", "pP", "S"},
            "central_peru": {"SKS"},
            "solomon_islands": {"P", "S"},
        }

    def test_initial_picks_are_the_labelled_headers(
        self, imported: Engine, three_component_data: dict[str, list[Path]]
    ) -> None:
        expected: dict[tuple[str, str, str], Timestamp] = {}
        for path in _event_files(three_component_data):
            sac = SAC.from_file(path)
            for name, header in _HEADERS.items():
                time = getattr(sac.timestamps, header)
                if time is not None:
                    expected[(path.parent.name, _stream(sac.station), name)] = time

        found: dict[tuple[str, str, str], Timestamp] = {}
        with Session(imported) as session:
            for phase in session.exec(select(AimbatPhase)).all():
                for row in phase.seismogram_parameters:
                    seismogram = row.seismogram
                    key = (_label(seismogram), _stream(seismogram.station), phase.name)
                    found[key] = row.initial_pick
        assert found.keys() == expected.keys()
        for key, pick in found.items():
            assert abs(pick - expected[key]) < Timedelta(milliseconds=1), key

    def test_second_source_for_a_stream_refused(
        self, imported: Engine, three_component_data: dict[str, list[Path]]
    ) -> None:
        """A rotated trace labelled as an existing horizontal is not added."""
        (rotated,) = three_component_data["special/rotated_as_bhn"]
        with Session(imported) as session:
            before = len(session.exec(select(AimbatSeismogram)).all())

        with pytest.raises(ValueError, match=re.escape("TA.POKR.--.BHN")):
            actions.add_data([rotated], DataType.SAC, engine=imported)

        with Session(imported) as session:
            assert len(session.exec(select(AimbatSeismogram)).all()) == before


class TestProcessing:
    """ICCS and MCCC on a phase whose seismograms differ in sampling rate."""

    def _phase_id(self, engine: Engine, label: str, name: str) -> uuid.UUID:
        with Session(engine) as session:
            for phase in session.exec(
                select(AimbatPhase).where(col(AimbatPhase.name) == name)
            ).all():
                if _label(phase.event.seismograms[0]) == label:
                    return phase.id
        raise LookupError((label, name))

    def test_p_at_mixed_rates(self, imported: Engine) -> None:
        """Channels of one site agree, whatever their location code or rate.

        The BH and LH streams of PAX are one sensor, which blocks
        processing, so the BH picks are removed first.
        """
        with Session(imported) as session:
            station_ids = session.exec(
                select(AimbatStation.id)
                .where(col(AimbatStation.name) == "PAX")
                .where(col(AimbatStation.channel).startswith("BH"))
            ).all()
        actions.remove_picks(
            PickSelection(station_ids=tuple(station_ids)), engine=imported
        )
        phase_id = self._phase_id(imported, "fiji_region", "P")
        actions.run_iccs(phase_id, autoflip=True, autoselect=True)
        actions.run_mccc(phase_id)

        residuals: dict[str, list[Timedelta]] = {}
        deltas: set[Timedelta] = set()
        with Session(imported) as session:
            assert Validity.read(session, phase_id).mccc(phase_id)
            phase = session.get_one(AimbatPhase, phase_id)
            for row in phase.seismogram_parameters:
                stream = _stream(row.seismogram.station)
                assert row.select and not row.flip, stream
                assert row.refined_pick is not None, stream
                residual = row.refined_pick - row.initial_pick
                assert abs(residual) < Timedelta(seconds=2), stream
                site = ".".join(stream.split(".")[:2])
                residuals.setdefault(site, []).append(residual)
                deltas.add(row.seismogram.delta)

        assert deltas == {Timedelta(seconds=s) for s in (0.025, 0.05, 1)}
        shared = {site: r for site, r in residuals.items() if len(r) > 1}
        assert shared.keys() == {"IU.COLA", "TA.TOLK"}
        for site, (first, *others) in shared.items():
            for other in others:
                assert abs(other - first) < Timedelta(seconds=0.25), site
