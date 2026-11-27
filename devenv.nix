{pkgs, ...}: {
  packages = with pkgs; [
    python313
    python315
  ];
  languages.python = {
    enable = true;
    package = pkgs.python314.withPackages (ps:
      with ps; [
        tkinter
        tox
      ]);
    venv.enable = true;
    uv = {
      enable = true;
      sync = {
        enable = true;
        allGroups = true;
      };
    };
  };
  scripts.reset-project.exec = ''
    set -euo pipefail
    export AIMBAT_LOG_LEVEL=DEBUG

    uv run aimbat project delete || true
    uv run aimbat project create

    iccs_events_dir=$(uv run python -c "from testkit.fixtures import ICCS_EVENTS_DIR; print(ICCS_EVENTS_DIR)")
    multi_phase_events_dir=$(uv run python -c "from testkit.fixtures import MULTI_PHASE_EVENTS_DIR; print(MULTI_PHASE_EVENTS_DIR)")

    # The ICCS events' picks are unlabelled predicted P arrivals in t0.
    uv run aimbat data add "$iccs_events_dir"/*/*.BHZ --no-progress --unlabelled-as P

    # The multi-phase event's P and pP picks are labelled.
    uv run aimbat data add "$multi_phase_events_dir"/*/*.BHZ --no-progress

    # Prepared three-component data, every pick on every channel: the
    # transverse channels of the events already added, the verticals of the
    # Fiji sites the multi-phase event lacks (the others would be second
    # sources), and every channel of the SKS event. PAX LH is left out, as it
    # repeats the BH streams of one sensor. Each component gives a phase.
    # P and pP are kept on Z, S on T, SKS on Q and T, and the phases on the
    # other components are removed.
    prepared_dir=$(uv run python -c "from testkit.fixtures import THREE_COMPONENT_EVENTS_DIR; print(THREE_COMPONENT_EVENTS_DIR / 'prepared')")
    uv run aimbat data add \
      "$prepared_dir"/{fiji_region,solomon_islands}/*.BHT \
      "$prepared_dir"/fiji_region/{AK.GRNC.--.BHZ,IU.COLA.*.BHZ,TA.TOLK.01.BHZ} \
      "$prepared_dir"/central_peru/* --no-progress
    uv run aimbat phase remove --event all --phase P --component T --yes
    uv run aimbat phase remove --event all --phase pP --component T --yes
    uv run aimbat phase remove --event all --phase S --component Z --yes
    uv run aimbat phase remove --event all --phase SKS --component Z --yes
    uv run aimbat phase remove --event all --phase SKS --component L --yes
  '';
}
