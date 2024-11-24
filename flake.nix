{
  description = "aimbat dev shell";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    nixgl.url = "github:nix-community/nixgl";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    nixgl,
    ...
  } @ inputs:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [nixgl.overlay];
        };
      in {
        devShells = {
          default = pkgs.mkShell {
            nativeBuildInputs = with pkgs; [
              poetry
              python313
              python311
              python312
              python312Packages.tox
              gnumake
              autoPatchelfHook
              sqlitebrowser
            ];

            shellHook = ''
              export LD_LIBRARY_PATH=${with pkgs;
                lib.makeLibraryPath [
                  stdenv.cc.cc.lib
                  zlib
                  zstd
                  xorg.libX11
                  libGL
                  glib
                  libxkbcommon
                  fontconfig
                  freetype
                  dbus
                  wayland
                ]}:$LD_LIBRARY_PATH
              VENV=.venv
              export POETRY_ACTIVE="true"
              export POETRY_VIRTUALENVS_IN_PROJECT="true"
              export MPLBACKEND=QtAgg
              poetry env use -- 3.13
              poetry install

              # Tox might fail on the first run if the bins aren't already there...
              autoPatchelf .tox/lint/bin/

              source $VENV/bin/activate
            '';
          };
        };
        formatter = pkgs.nixpkgs-fmt;
      }
    );
}
