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
  '';
}
