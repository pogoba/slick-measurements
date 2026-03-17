{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };

  outputs = { self, ...} @ inputs: let
    pkgs = inputs.nixpkgs.legacyPackages.x86_64-linux;
  in {

    packages.x86_64-linux.hello = pkgs.hello;

    packages.x86_64-linux.default = self.packages.x86_64-linux.hello;

    devShells.x86_64-linux.default = pkgs.mkShell {
      name = "hello";
      nativeBuildInputs = [ pkgs.qt6.wrapQtAppsHook ];
      buildInputs = (with pkgs.python3.pkgs; [
        black # auto formatting
        flake8 # annoying "good practice" annotations
        mypy # static typing
        pkgs.ruff # language server ("linting")

        numpy
        matplotlib
        seaborn
        tqdm
        scipy
        plotly
        pyqt6
        pyqt6-webengine

        bpython
        ptpython
        ipykernel

        marimo
      ]) ++ [
        pkgs.qt6.qtwayland
      ];
    };
  };
}
