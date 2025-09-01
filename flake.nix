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
              python312
              python313
              python313Packages.tox
              gnumake
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
              uv sync
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
