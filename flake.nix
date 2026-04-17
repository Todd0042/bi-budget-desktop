{
  description = "BiBudget packaged as a Nix app";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        python = pkgs.python312;
        pythonEnv = python.withPackages (ps: [
          ps.pyside6
        ]);
      in
      {
        packages.default = pkgs.stdenv.mkDerivation {
          pname = "bibudget";
          version = "1.0";

          src = ./.;

          buildInputs = [ pythonEnv ];

          installPhase = ''
            mkdir -p $out/bin
            mkdir -p $out/app

            # Copy your source code
            cp -r $src/* $out/app/

            # Create launcher script
            cat > $out/bin/bibudget <<EOF
#!${pythonEnv}/bin/python
import sys
sys.path.insert(0, "$out/app")
import main
EOF

            chmod +x $out/bin/bibudget
          '';
        };
      }
    );
}
