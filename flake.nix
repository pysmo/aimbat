{
  description = "aimbat dev shell";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = nixpkgs.legacyPackages.${system};
      in {
        devShells = {
          default = pkgs.mkShell {
            nativeBuildInputs = with pkgs; [
              gnumake
              autoPatchelfHook
              sqlitebrowser
              poetry
              python313Full
              python310
              python311
              python312
              python312Packages.tox
            ];

            shellHook = ''
              export LD_LIBRARY_PATH=${with pkgs;
                lib.makeLibraryPath [
                  stdenv.cc.cc.lib
                  zlib
                ]}:$LD_LIBRARY_PATH
              VENV=.venv
              export POETRY_ACTIVE="true"
              export POETRY_VIRTUALENVS_IN_PROJECT="true"
              export POETRY_VIRTUALENVS_OPTIONS_SYSTEM_SITE_PACKAGES="true"
              export MPLBACKEND=TkAgg
              poetry env use -- 3.13
              poetry install

              # Tox might fail on the first run if the bins aren't already there...
              autoPatchelf .tox/lint/bin/

              source $VENV/bin/activate
            '';
          };
        };
        formatter = nixpkgs.legacyPackages.${system}.nixpkgs-fmt;
      }
    );
}
