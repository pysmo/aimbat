{
  description = "aimbat dev shell";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      forEachSystem = nixpkgs.lib.genAttrs [
        "aarch64-linux"
        "i686-linux"
        "x86_64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];
    in
    {
      devShells = forEachSystem
        (
          system:
          let
            pkgs = nixpkgs.legacyPackages.${system};
          in
          {
            default = pkgs.mkShell {
              nativeBuildInputs = with pkgs; [
                gnumake
                poetry
                python312
                python311
                python310
                python312Packages.tox
                autoPatchelfHook
                sqlitebrowser
              ];

              shellHook = ''
                export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath [
                  pkgs.stdenv.cc.cc.lib
                  pkgs.zlib
                ]}:$LD_LIBRARY_PATH
                VENV=.venv
                export POETRY_ACTIVE="true"
                export POETRY_VIRTUALENVS_IN_PROJECT="true"
                export POETRY_VIRTUALENVS_PATH=$VENV
                if test ! -d $VENV; then
                  poetry env use -- 3.12
                  poetry install
                fi
                autoPatchelf .venv/bin/ .tox/lint/bin/
                source $VENV/bin/activate
              '';
            };
          }
        );
      formatter = forEachSystem (system: nixpkgs.legacyPackages.${system}.nixpkgs-fmt);
    };
}
