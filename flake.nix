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
              uv
              ruff
              (python314.withPackages (ps: with ps; [tox]))
              python313
              python312
              gnumake
              sqlitebrowser
            ];

            shellHook = ''
              export LD_LIBRARY_PATH=${with pkgs;
                lib.makeLibraryPath [
                  stdenv.cc.cc.lib
                  zlib
                  zstd
                  libX11
                  libGL
                  glib
                  libxkbcommon
                  fontconfig
                  freetype
                  dbus
                  wayland
                ]}:$LD_LIBRARY_PATH
                export UV_PYTHON=$(which python3.14)
                export UV_NO_MANAGED_PYTHON=true
                [ ! -d .venv ] && uv venv --system-site-packages
                uv sync --locked --all-extras
                VENV=.venv
                export MPLBACKEND=QtAgg
                source $VENV/bin/activate
            '';
          };
        };
        formatter = pkgs.nixpkgs-fmt;
      }
    );
}
