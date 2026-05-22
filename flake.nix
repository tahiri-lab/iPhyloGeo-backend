{
  description = "dev shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            python310
            python310Packages.pip

            # LSP
            pyright
            ruff

            # DAP
            python310Packages.debugpy
          ];

          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
            pkgs.stdenv.cc.cc.lib
          ];

          shellHook = ''
            echo "Entering dev shell"

            # optional: auto-create venv if missing
            if [ ! -d .venv ]; then
              python -m venv .venv
            fi

            source .venv/bin/activate
          '';
        };
      });
}
