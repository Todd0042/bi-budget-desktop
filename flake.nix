{
  description = "Bi-Budget Desktop (Python + PySide6)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pkgs.python313
            pkgs.python313Packages.pyside6
            pkgs.qt6.full
          ];

          # Makes Qt apps (like PySide6) find their plugins
          QT_PLUGIN_PATH = "${pkgs.qt6.full}/lib/qt-6/plugins";
          QML2_IMPORT_PATH = "${pkgs.qt6.full}/lib/qt-6/qml";
        };
      });
}
