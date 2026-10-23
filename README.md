# NEST

NEST is a desktop business decision-support tool for comparing two strategic business options using financial analysis and numerical methods.

## What NEST Does

NEST helps users compare two alternatives by entering:

- Revenue per unit
- Expected volume
- Fixed costs
- Variable costs

The application calculates:

- Profit
- Break-even point
- Crossover point
- Cost drivers
- Sensitivity impact
- Final recommendation

## Architecture

The project uses a layered architecture:

- **Python UI**: handles the interface, charts, user input, and visualization
- **C# Logic Layer**: contains the business and numerical calculation logic
- **JSON + subprocess**: connects Python with the compiled C# logic executable
- **PyInstaller**: packages the Python application into a desktop executable
![NEST Architecture](assets/architecture.png)
## Numerical Methods

NEST includes several root-finding methods:

- Bisection
- Newton-Raphson
- Secant
- Brent
- Combined Bisection-Newton method

These methods are used to solve equations such as break-even and crossover calculations.

## Technologies Used

- Python
- CustomTkinter
- Matplotlib
- C#
- JSON
- PyInstaller

## How to Run

1. Download [NEST.exe](https://github.com/victoriazakarian/NEST/raw/refs/heads/main/NEST.exe).
2. Open the executable on Windows.
3. Enter the financial data for two business alternatives.
4. Run the analysis to view calculations, visualizations, and recommendations.

**No Python or C# installation is required.** The executable includes the components needed to run the application.

**Note:** Windows SmartScreen may display a warning because the executable is not digitally signed.

## Source Code

- `nest.py` — Python user interface and visualization code.
- `logic.zip` — C# calculation engine source code.
- `NEST.exe` — Standalone Windows application.
