NEST – Numerical Evaluation & Strategic Toolkit

NEST is a desktop business decision-support application designed to compare strategic options using financial analysis and numerical methods.

🚀 Overview

The application allows users to model and compare two business alternatives by defining:

Revenue per unit
Fixed and variable costs
Expected volume

Based on these inputs, NEST computes:

Profit functions
Break-even points
Crossover points
Cost structure analysis
Sensitivity analysis
Final recommendation
🧠 Architecture

The project follows a layered architecture:

Python (UI Layer)
Handles user interaction, visualization, and charts.
C# (Logic Layer)
Implements business logic and numerical computation.
Communication
Python calls the compiled C# executable (logic.exe) using subprocess and exchanges data via JSON.
⚙️ Numerical Methods

NEST implements multiple root-finding algorithms:

Bisection
Newton-Raphson
Secant
Brent
Combined (Bisection–Newton)

These methods are used to solve business equations such as break-even and crossover points.

📦 Build & Run
Run application

Execute:

NEST.exe
🛠 Technologies
Python (customtkinter, matplotlib)
C# (.NET)
JSON for data exchange
PyInstaller for packaging
📊 Features
Business option comparison
Break-even analysis
Profit visualization
Sensitivity analysis
Automatic recommendation
📌 Notes
The .exe file is a packaged version of the Python UI.
The system is designed with separation of concerns between UI and logic layers.
C# logic can be extended or replaced with other backends if needed.
