{
  description = "Dev shell to work on this project with the Nix package manager";

  inputs = {
    # The latest NixPkgs removed the Python version we need so we use an older one
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

            # LSP (language servers)
            pyright
            ruff

            # DAP (debugging tooling)
            python310Packages.debugpy
          ];

          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath (with pkgs; [
            # Pip needs a working standard environment to compile stuff
            stdenv.cc.cc.lib

            # Why the hell is the package with libmagic named file?? lmao
            file # libmagic
          ]);

          # Auto-setup the Python venv
          shellHook = ''
            echo "Entering dev shell"

            if [ ! -d .venv ]; then
              python -m venv .venv
            fi

            source .venv/bin/activate
          '';
        };
      });
}
