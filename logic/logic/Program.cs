using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace NEST.Logic
{
    // ============================================================
    // DATA MODELS
    // ============================================================

    public class CostComponent
    {
        public string Name { get; set; }
        public double Amount { get; set; }
        public string CostType { get; set; }   // "fixed" or "variable"
        public string Category { get; set; }
        public string Notes { get; set; }

        public CostComponent(
            string name,
            double amount,
            string costType = "fixed",
            string category = "general",
            string notes = "")
        {
            Name = string.IsNullOrWhiteSpace(name) ? "Unnamed" : name;
            Amount = amount;
            CostType = string.IsNullOrWhiteSpace(costType) ? "fixed" : costType.ToLowerInvariant();
            Category = string.IsNullOrWhiteSpace(category) ? "general" : category;
            Notes = notes ?? "";
        }

        public double CostAt(double x)
        {
            if (CostType == "fixed")
                return Amount;

            if (CostType == "variable")
                return Amount * x;

            return Amount;
        }

        public CostComponent Clone()
        {
            return new CostComponent(Name, Amount, CostType, Category, Notes);
        }
    }

    public class BusinessOption
    {
        public string Name { get; set; }
        public double RevenuePerUnit { get; set; }
        public double ExpectedVolume { get; set; }
        public string Description { get; set; }
        public List<CostComponent> CostComponents { get; set; }

        public BusinessOption(
            string name,
            double revenuePerUnit = 0.0,
            double expectedVolume = 0.0,
            string description = "",
            List<CostComponent>? costComponents = null)
        {
            Name = string.IsNullOrWhiteSpace(name) ? "Option" : name;
            RevenuePerUnit = revenuePerUnit;
            ExpectedVolume = expectedVolume;
            Description = description ?? "";
            CostComponents = costComponents ?? new List<CostComponent>();
        }

        public double TotalRevenue(double x)
        {
            return RevenuePerUnit * x;
        }

        public double TotalCost(double x)
        {
            return CostComponents.Sum(c => c.CostAt(x));
        }

        public double Profit(double x)
        {
            return TotalRevenue(x) - TotalCost(x);
        }

        public double CostPerUnit(double x)
        {
            if (Math.Abs(x) < 1e-15)
                return double.PositiveInfinity;

            return TotalCost(x) / x;
        }

        public double Margin(double x)
        {
            double revenue = TotalRevenue(x);

            if (Math.Abs(revenue) < 1e-15)
                return 0.0;

            return Profit(x) / revenue * 100.0;
        }

        public double FixedTotal()
        {
            return CostComponents
                .Where(c => c.CostType == "fixed")
                .Sum(c => c.Amount);
        }

        public double VariableRate()
        {
            return CostComponents
                .Where(c => c.CostType == "variable")
                .Sum(c => c.Amount);
        }

        public List<CostBreakdownRow> CostBreakdown(double x)
        {
            double total = TotalCost(x);
            var rows = new List<CostBreakdownRow>();

            foreach (var c in CostComponents)
            {
                double amount = c.CostAt(x);
                double percent = total > 0.0 ? amount / total * 100.0 : 0.0;

                rows.Add(new CostBreakdownRow(
                    c.Name,
                    c.Category,
                    amount,
                    percent
                ));
            }

            return rows
                .OrderByDescending(r => r.Amount)
                .ToList();
        }

        public BusinessOption Clone()
        {
            return new BusinessOption(
                Name,
                RevenuePerUnit,
                ExpectedVolume,
                Description,
                CostComponents.Select(c => c.Clone()).ToList()
            );
        }
    }

    public class CostBreakdownRow
    {
        public string Component { get; set; }
        public string Category { get; set; }
        public double Amount { get; set; }
        public double PercentOfTotal { get; set; }

        public CostBreakdownRow(string component, string category, double amount, double percentOfTotal)
        {
            Component = component;
            Category = category;
            Amount = amount;
            PercentOfTotal = percentOfTotal;
        }
    }

    // ============================================================
    // NUMERICAL ENGINE
    // ============================================================

    public class MethodResult
    {
        public double? Root { get; set; }
        public int Iterations { get; set; }
        public double? Error { get; set; }
        public string Status { get; set; }

        public MethodResult(double? root, int iterations, double? error, string status)
        {
            Root = root;
            Iterations = iterations;
            Error = error;
            Status = status;
        }
    }

    public class NumericalResult
    {
        public Dictionary<string, MethodResult> Results { get; set; }
        public List<double> Roots { get; set; }
        public string? BestMethodName { get; set; }
        public MethodResult? BestResult { get; set; }

        public NumericalResult(
            Dictionary<string, MethodResult> results,
            List<double> roots,
            string? bestMethodName,
            MethodResult? bestResult)
        {
            Results = results;
            Roots = roots;
            BestMethodName = bestMethodName;
            BestResult = bestResult;
        }
    }

    public static class NumericalEngine
    {
        public const double DefaultTolerance = 1e-8;
        public const int DefaultMaxIterations = 200;
        public const int ScanSteps = 4000;

        private static bool IsSafe(double v)
        {
            return !double.IsNaN(v) && !double.IsInfinity(v);
        }

        private static double? NormalizeZero(double? v, double eps = 1e-14)
        {
            if (v == null)
                return null;

            if (!IsSafe(v.Value))
                return null;

            return Math.Abs(v.Value) < eps ? 0.0 : v.Value;
        }

        private static bool SameRoot(double a, double b, double tolerance = 1e-6)
        {
            return Math.Abs(a - b) <= tolerance;
        }

        public static List<double> UniqueSortedRoots(IEnumerable<double> roots, double tolerance = 1e-6)
        {
            var clean = new List<double>();

            foreach (double r in roots.OrderBy(x => x))
            {
                if (!IsSafe(r))
                    continue;

                if (clean.Count == 0 || !SameRoot(r, clean[^1], tolerance))
                    clean.Add(r);
            }

            return clean;
        }

        private static bool ResultBetter(MethodResult? candidate, MethodResult? best, double errorTieTolerance = 1e-12)
        {
            if (candidate == null)
                return false;

            if (candidate.Status != "Success" || candidate.Root == null || candidate.Error == null)
                return false;

            if (best == null)
                return true;

            if (best.Error == null)
                return true;

            if (candidate.Error.Value < best.Error.Value - errorTieTolerance)
                return true;

            if (Math.Abs(candidate.Error.Value - best.Error.Value) <= errorTieTolerance &&
                candidate.Iterations < best.Iterations)
                return true;

            return false;
        }

        public static (string? Name, MethodResult? Result) ChooseBestMethod(Dictionary<string, MethodResult> results)
        {
            string? bestName = null;
            MethodResult? bestData = null;

            foreach (var pair in results)
            {
                if (ResultBetter(pair.Value, bestData))
                {
                    bestName = pair.Key;
                    bestData = pair.Value;
                }
            }

            return (bestName, bestData);
        }

        public static MethodResult Bisection(
            Func<double, double> f,
            double a,
            double b,
            double tolerance = DefaultTolerance,
            int maxIterations = DefaultMaxIterations)
        {
            double? fa = NormalizeZero(SafeEval(f, a));
            double? fb = NormalizeZero(SafeEval(f, b));

            if (fa == null || fb == null)
                return new MethodResult(null, 0, null, "Failed");

            if (Math.Abs(fa.Value) < tolerance)
                return new MethodResult(a, 0, Math.Abs(fa.Value), "Success");

            if (Math.Abs(fb.Value) < tolerance)
                return new MethodResult(b, 0, Math.Abs(fb.Value), "Success");

            if (fa.Value * fb.Value > 0.0)
                return new MethodResult(null, 0, null, "No bracket");

            double c = a;

            for (int i = 1; i <= maxIterations; i++)
            {
                c = (a + b) / 2.0;
                double? fc = NormalizeZero(SafeEval(f, c));

                if (fc == null)
                    return new MethodResult(null, i, null, "Failed");

                if (Math.Abs(fc.Value) < tolerance || Math.Abs(b - a) < tolerance)
                    return new MethodResult(c, i, Math.Abs(fc.Value), "Success");

                if (fa.Value * fc.Value < 0.0)
                {
                    b = c;
                    fb = fc;
                }
                else
                {
                    a = c;
                    fa = fc;
                }
            }

            double? last = NormalizeZero(SafeEval(f, c));
            return new MethodResult(c, maxIterations, last == null ? null : Math.Abs(last.Value), "Max iter");
        }

        public static double? NumericalDerivative(Func<double, double> f, double x, double h = 1e-5)
        {
            double? fph = NormalizeZero(SafeEval(f, x + h));
            double? fmh = NormalizeZero(SafeEval(f, x - h));

            if (fph == null || fmh == null)
                return null;

            return (fph.Value - fmh.Value) / (2.0 * h);
        }

        public static MethodResult Newton(
            Func<double, double> f,
            double? x0,
            double tolerance = DefaultTolerance,
            int maxIterations = DefaultMaxIterations)
        {
            if (x0 == null)
                return new MethodResult(null, 0, null, "No start");

            double curr = x0.Value;

            for (int i = 1; i <= maxIterations; i++)
            {
                double? fv = NormalizeZero(SafeEval(f, curr));

                if (fv == null)
                    return new MethodResult(null, i, null, "Failed");

                double? dfv = NumericalDerivative(f, curr);

                if (dfv == null || Math.Abs(dfv.Value) < 1e-14)
                    return new MethodResult(null, i, null, "Zero deriv");

                double next = curr - fv.Value / dfv.Value;

                if (!IsSafe(next) || Math.Abs(next) > 1e9)
                    return new MethodResult(null, i, null, "Diverged");

                double? fNext = NormalizeZero(SafeEval(f, next));

                if (fNext == null)
                    return new MethodResult(null, i, null, "Failed");

                if (Math.Abs(next - curr) < tolerance && Math.Abs(fNext.Value) < tolerance)
                    return new MethodResult(next, i, Math.Abs(fNext.Value), "Success");

                curr = next;
            }

            double? finalValue = NormalizeZero(SafeEval(f, curr));
            return new MethodResult(curr, maxIterations, finalValue == null ? null : Math.Abs(finalValue.Value), "Max iter");
        }

        public static MethodResult Secant(
            Func<double, double> f,
            double? x0,
            double? x1,
            double tolerance = DefaultTolerance,
            int maxIterations = DefaultMaxIterations)
        {
            if (x0 == null || x1 == null)
                return new MethodResult(null, 0, null, "No start");

            double a = x0.Value;
            double b = x1.Value;

            double? fa = NormalizeZero(SafeEval(f, a));
            double? fb = NormalizeZero(SafeEval(f, b));

            if (fa == null || fb == null)
                return new MethodResult(null, 0, null, "Failed");

            for (int i = 1; i <= maxIterations; i++)
            {
                double denominator = fb.Value - fa.Value;

                if (Math.Abs(denominator) < 1e-15)
                    return new MethodResult(null, i, null, "Zero denom");

                double next = b - fb.Value * (b - a) / denominator;

                if (!IsSafe(next) || Math.Abs(next) > 1e9)
                    return new MethodResult(null, i, null, "Diverged");

                double? fNext = NormalizeZero(SafeEval(f, next));

                if (fNext == null)
                    return new MethodResult(null, i, null, "Failed");

                if (Math.Abs(next - b) < tolerance && Math.Abs(fNext.Value) < tolerance)
                    return new MethodResult(next, i, Math.Abs(fNext.Value), "Success");

                a = b;
                fa = fb;

                b = next;
                fb = fNext;
            }

            return new MethodResult(b, maxIterations, Math.Abs(fb.Value), "Max iter");
        }

        public static MethodResult Brent(
            Func<double, double> f,
            double a,
            double b,
            double tolerance = DefaultTolerance,
            int maxIterations = DefaultMaxIterations)
        {
            double? faN = NormalizeZero(SafeEval(f, a));
            double? fbN = NormalizeZero(SafeEval(f, b));

            if (faN == null || fbN == null)
                return new MethodResult(null, 0, null, "Failed");

            double fa = faN.Value;
            double fb = fbN.Value;

            if (Math.Abs(fa) < tolerance)
                return new MethodResult(a, 0, Math.Abs(fa), "Success");

            if (Math.Abs(fb) < tolerance)
                return new MethodResult(b, 0, Math.Abs(fb), "Success");

            if (fa * fb > 0.0)
                return new MethodResult(null, 0, null, "No bracket");

            if (Math.Abs(fa) < Math.Abs(fb))
            {
                Swap(ref a, ref b);
                Swap(ref fa, ref fb);
            }

            double c = a;
            double fc = fa;
            bool mflag = true;
            double? d = null;
            double s = b;

            for (int i = 1; i <= maxIterations; i++)
            {
                if (Math.Abs(b - a) < tolerance || Math.Abs(fb) < tolerance)
                    return new MethodResult(b, i, Math.Abs(fb), "Success");

                if (Math.Abs(fa - fc) > 1e-15 && Math.Abs(fb - fc) > 1e-15)
                {
                    s =
                        a * fb * fc / ((fa - fb) * (fa - fc)) +
                        b * fa * fc / ((fb - fa) * (fb - fc)) +
                        c * fa * fb / ((fc - fa) * (fc - fb));
                }
                else
                {
                    if (Math.Abs(fb - fa) < 1e-15)
                        s = (a + b) / 2.0;
                    else
                        s = b - fb * (b - a) / (fb - fa);
                }

                bool cond1 = !(Math.Min(a, b) < s && s < Math.Max(a, b));
                bool cond2 = mflag && Math.Abs(s - b) >= Math.Abs(b - c) / 2.0;
                bool cond3 = !mflag && d != null && Math.Abs(s - b) >= Math.Abs(c - d.Value) / 2.0;
                bool cond4 = mflag && Math.Abs(b - c) < tolerance;
                bool cond5 = !mflag && d != null && Math.Abs(c - d.Value) < tolerance;

                if (cond1 || cond2 || cond3 || cond4 || cond5)
                {
                    s = (a + b) / 2.0;
                    mflag = true;
                }
                else
                {
                    mflag = false;
                }

                double? fsN = NormalizeZero(SafeEval(f, s));

                if (fsN == null)
                    return new MethodResult(null, i, null, "Failed");

                double fs = fsN.Value;

                d = c;
                c = b;
                fc = fb;

                if (fa * fs < 0.0)
                {
                    b = s;
                    fb = fs;
                }
                else
                {
                    a = s;
                    fa = fs;
                }

                if (Math.Abs(fa) < Math.Abs(fb))
                {
                    Swap(ref a, ref b);
                    Swap(ref fa, ref fb);
                }
            }

            return new MethodResult(b, maxIterations, Math.Abs(fb), "Max iter");
        }

        public static MethodResult BisectionNewton(
            Func<double, double> f,
            double a,
            double b,
            double tolerance = DefaultTolerance,
            int maxIterations = DefaultMaxIterations)
        {
            double? fa = NormalizeZero(SafeEval(f, a));
            double? fb = NormalizeZero(SafeEval(f, b));

            if (fa == null || fb == null)
                return new MethodResult(null, 0, null, "Failed");

            if (Math.Abs(fa.Value) < tolerance)
                return new MethodResult(a, 0, Math.Abs(fa.Value), "Success");

            if (Math.Abs(fb.Value) < tolerance)
                return new MethodResult(b, 0, Math.Abs(fb.Value), "Success");

            if (fa.Value * fb.Value > 0.0)
                return new MethodResult(null, 0, null, "No bracket");

            int bisectionPhases = maxIterations / 3;
            double curr = (a + b) / 2.0;

            for (int i = 1; i <= bisectionPhases; i++)
            {
                curr = (a + b) / 2.0;
                double? fc = NormalizeZero(SafeEval(f, curr));

                if (fc == null)
                    return new MethodResult(null, i, null, "Failed");

                if (Math.Abs(fc.Value) < tolerance || Math.Abs(b - a) < tolerance)
                    return new MethodResult(curr, i, Math.Abs(fc.Value), "Success");

                if (fa.Value * fc.Value < 0.0)
                {
                    b = curr;
                    fb = fc;
                }
                else
                {
                    a = curr;
                    fa = fc;
                }
            }

            int totalIterations = bisectionPhases;

            for (int j = 1; j <= maxIterations - bisectionPhases; j++)
            {
                double? fv = NormalizeZero(SafeEval(f, curr));

                if (fv == null)
                    return new MethodResult(null, totalIterations + j, null, "Failed");

                double? dfv = NumericalDerivative(f, curr);

                if (dfv == null || Math.Abs(dfv.Value) < 1e-14)
                {
                    curr = (a + b) / 2.0;
                    continue;
                }

                double next = curr - fv.Value / dfv.Value;

                if (next < a || next > b)
                    next = (a + b) / 2.0;

                double? fNext = NormalizeZero(SafeEval(f, next));

                if (fNext == null)
                    return new MethodResult(null, totalIterations + j, null, "Failed");

                if (Math.Abs(next - curr) < tolerance && Math.Abs(fNext.Value) < tolerance)
                    return new MethodResult(next, totalIterations + j, Math.Abs(fNext.Value), "Success");

                if (fa.Value * fNext.Value < 0.0)
                {
                    b = next;
                    fb = fNext;
                }
                else
                {
                    a = next;
                    fa = fNext;
                }

                curr = next;
            }

            double? last = NormalizeZero(SafeEval(f, curr));
            return new MethodResult(curr, maxIterations, last == null ? null : Math.Abs(last.Value), "Max iter");
        }

        public static (List<(double A, double B)> Brackets, List<double> ExactRoots) FindBrackets(
            Func<double, double> f,
            double lo,
            double hi,
            int steps = ScanSteps,
            double zeroTolerance = 1e-10)
        {
            var brackets = new List<(double A, double B)>();
            var exact = new List<double>();

            double prevX = lo;
            double? prevF = NormalizeZero(SafeEval(f, prevX));

            if (prevF != null && Math.Abs(prevF.Value) < zeroTolerance)
                exact.Add(prevX);

            for (int i = 1; i < steps; i++)
            {
                double x = lo + (hi - lo) * i / (steps - 1.0);
                double? fx = NormalizeZero(SafeEval(f, x));

                if (fx == null)
                {
                    prevX = x;
                    prevF = fx;
                    continue;
                }

                if (Math.Abs(fx.Value) < zeroTolerance)
                    exact.Add(x);

                if (prevF != null && prevF.Value * fx.Value < 0.0)
                    brackets.Add((prevX, x));

                prevX = x;
                prevF = fx;
            }

            var cleanBrackets = new List<(double A, double B)>();

            foreach (var bracket in brackets)
            {
                bool exists = cleanBrackets.Any(
                    existing =>
                        Math.Abs(bracket.A - existing.A) < 1e-6 &&
                        Math.Abs(bracket.B - existing.B) < 1e-6
                );

                if (!exists)
                    cleanBrackets.Add(bracket);
            }

            return (cleanBrackets, UniqueSortedRoots(exact));
        }

        public static NumericalResult RunAllMethods(Func<double, double> f, double lo, double hi)
        {
            var scan = FindBrackets(f, lo, hi);
            var brackets = scan.Brackets;
            var exact = scan.ExactRoots;

            var results = new Dictionary<string, MethodResult>();
            var allRoots = new List<double>();

            MethodResult? bestBisection = null;

            if (brackets.Count > 0)
            {
                foreach (var (a, b) in brackets)
                {
                    var candidate = Bisection(f, a, b);

                    if (candidate.Status == "Success" && candidate.Root != null)
                    {
                        allRoots.Add(candidate.Root.Value);

                        if (ResultBetter(candidate, bestBisection))
                            bestBisection = candidate;
                    }
                }

                results["Bisection"] = bestBisection ?? new MethodResult(null, 0, null, "No bracket");
            }
            else
            {
                results["Bisection"] = new MethodResult(null, 0, null, "No bracket");
            }

            MethodResult? bestBrent = null;

            if (brackets.Count > 0)
            {
                foreach (var (a, b) in brackets)
                {
                    var candidate = Brent(f, a, b);

                    if (candidate.Status == "Success" && candidate.Root != null)
                    {
                        allRoots.Add(candidate.Root.Value);

                        if (ResultBetter(candidate, bestBrent))
                            bestBrent = candidate;
                    }
                }

                results["Brent"] = bestBrent ?? new MethodResult(null, 0, null, "No bracket");
            }
            else
            {
                results["Brent"] = new MethodResult(null, 0, null, "No bracket");
            }

            MethodResult? bestNewton = null;
            var newtonStarts = brackets.Count > 0
                ? brackets.Select(bracket => (bracket.A + bracket.B) / 2.0).ToList()
                : new List<double> { (lo + hi) / 2.0 };

            foreach (double x0 in newtonStarts)
            {
                var candidate = Newton(f, x0);

                if (candidate.Status == "Success" &&
                    candidate.Root != null &&
                    candidate.Root.Value >= lo &&
                    candidate.Root.Value <= hi)
                {
                    allRoots.Add(candidate.Root.Value);

                    if (ResultBetter(candidate, bestNewton))
                        bestNewton = candidate;
                }
            }

            results["Newton"] = bestNewton ?? new MethodResult(null, 0, null, "Failed");

            MethodResult? bestSecant = null;
            var secantPairs = brackets.Count > 0
                ? brackets
                : new List<(double A, double B)> { ((lo + hi) / 2.0 - 1.0, (lo + hi) / 2.0 + 1.0) };

            foreach (var (a, b) in secantPairs)
            {
                var candidate = Secant(f, a, b);

                if (candidate.Status == "Success" &&
                    candidate.Root != null &&
                    candidate.Root.Value >= lo &&
                    candidate.Root.Value <= hi)
                {
                    allRoots.Add(candidate.Root.Value);

                    if (ResultBetter(candidate, bestSecant))
                        bestSecant = candidate;
                }
            }

            results["Secant"] = bestSecant ?? new MethodResult(null, 0, null, "Failed");

            MethodResult? bestHybrid = null;

            if (brackets.Count > 0)
            {
                foreach (var (a, b) in brackets)
                {
                    var candidate = BisectionNewton(f, a, b);

                    if (candidate.Status == "Success" && candidate.Root != null)
                    {
                        allRoots.Add(candidate.Root.Value);

                        if (ResultBetter(candidate, bestHybrid))
                            bestHybrid = candidate;
                    }
                }

                results["Bisection-Newton"] = bestHybrid ?? new MethodResult(null, 0, null, "No bracket");
            }
            else
            {
                results["Bisection-Newton"] = new MethodResult(null, 0, null, "No bracket");
            }

            allRoots.AddRange(exact);

            var uniqueRoots = UniqueSortedRoots(allRoots);
            var best = ChooseBestMethod(results);

            return new NumericalResult(results, uniqueRoots, best.Name, best.Result);
        }

        private static double? SafeEval(Func<double, double> f, double x)
        {
            try
            {
                double value = f(x);
                return IsSafe(value) ? value : null;
            }
            catch
            {
                return null;
            }
        }

        private static void Swap(ref double a, ref double b)
        {
            (a, b) = (b, a);
        }
    }

    // ============================================================
    // COMPARISON ENGINE
    // ============================================================

    public class SummaryResult
    {
        public double VolumeA { get; set; }
        public double VolumeB { get; set; }
        public double ProfitA { get; set; }
        public double ProfitB { get; set; }
        public double MarginA { get; set; }
        public double MarginB { get; set; }
        public double CostPerUnitA { get; set; }
        public double CostPerUnitB { get; set; }
        public string Better { get; set; }

        public SummaryResult(
            double volumeA,
            double volumeB,
            double profitA,
            double profitB,
            double marginA,
            double marginB,
            double costPerUnitA,
            double costPerUnitB,
            string better)
        {
            VolumeA = volumeA;
            VolumeB = volumeB;
            ProfitA = profitA;
            ProfitB = profitB;
            MarginA = marginA;
            MarginB = marginB;
            CostPerUnitA = costPerUnitA;
            CostPerUnitB = costPerUnitB;
            Better = better;
        }
    }

    public class ComparisonEngine
    {
        public BusinessOption A { get; }
        public BusinessOption B { get; }

        public ComparisonEngine(BusinessOption optionA, BusinessOption optionB)
        {
            A = optionA;
            B = optionB;
        }

        public double ProfitDifference(double x)
        {
            return A.Profit(x) - B.Profit(x);
        }

        public (double Lo, double Hi) ScanRange()
        {
            double volume = Math.Max(Math.Max(A.ExpectedVolume, B.ExpectedVolume), 100.0);
            return (0.1, volume * 2.5);
        }

        public double? FindBreakEvenA()
        {
            var (lo, hi) = ScanRange();
            var result = NumericalEngine.RunAllMethods(A.Profit, lo, hi);
            return result.Roots.Count > 0 ? result.Roots[0] : null;
        }

        public double? FindBreakEvenB()
        {
            var (lo, hi) = ScanRange();
            var result = NumericalEngine.RunAllMethods(B.Profit, lo, hi);
            return result.Roots.Count > 0 ? result.Roots[0] : null;
        }

        public NumericalResult FindCrossover()
        {
            var (lo, hi) = ScanRange();
            return NumericalEngine.RunAllMethods(ProfitDifference, lo, hi);
        }

        public double? AnalyticCrossover()
        {
            double slopeA = A.RevenuePerUnit - A.VariableRate();
            double slopeB = B.RevenuePerUnit - B.VariableRate();

            double fixedA = A.FixedTotal();
            double fixedB = B.FixedTotal();

            double denominator = slopeA - slopeB;

            if (Math.Abs(denominator) < 1e-12)
                return null;

            double root = (fixedA - fixedB) / denominator;

            if (root < 0.0 || double.IsNaN(root) || double.IsInfinity(root))
                return null;

            return root;
        }

        public SummaryResult SummaryAtVolumes(double volumeA, double volumeB)
        {
            double profitA = A.Profit(volumeA);
            double profitB = B.Profit(volumeB);

            string better = profitA >= profitB ? A.Name : B.Name;

            return new SummaryResult(
                volumeA,
                volumeB,
                profitA,
                profitB,
                A.Margin(volumeA),
                B.Margin(volumeB),
                A.CostPerUnit(volumeA),
                B.CostPerUnit(volumeB),
                better
            );
        }
    }

    // ============================================================
    // SENSITIVITY ENGINE
    // ============================================================

    public class SensitivityResult
    {
        public string Component { get; set; }
        public string Category { get; set; }
        public double ProfitImpact { get; set; }
        public double AbsoluteImpact { get; set; }

        public SensitivityResult(string component, string category, double profitImpact, double absoluteImpact)
        {
            Component = component;
            Category = category;
            ProfitImpact = profitImpact;
            AbsoluteImpact = absoluteImpact;
        }
    }

    public class SensitivityEngine
    {
        public BusinessOption Option { get; }

        public SensitivityEngine(BusinessOption option)
        {
            Option = option;
        }

        public double TestComponent(string componentName, double percentChange, double x)
        {
            var optionCopy = Option.Clone();

            foreach (var c in optionCopy.CostComponents)
            {
                if (c.Name == componentName)
                    c.Amount *= 1.0 + percentChange / 100.0;
            }

            return optionCopy.Profit(x);
        }

        public List<SensitivityResult> RankSensitivity(double x, double percentChange = 10.0)
        {
            double baseProfit = Option.Profit(x);
            var impacts = new List<SensitivityResult>();

            foreach (var c in Option.CostComponents)
            {
                double newProfit = TestComponent(c.Name, percentChange, x);
                double delta = newProfit - baseProfit;

                impacts.Add(new SensitivityResult(
                    c.Name,
                    c.Category,
                    delta,
                    Math.Abs(delta)
                ));
            }

            return impacts
                .OrderByDescending(i => i.AbsoluteImpact)
                .ToList();
        }
    }

    // ============================================================
    // RECOMMENDATION ENGINE
    // ============================================================

    public class RecommendationEngine
    {
        private readonly ComparisonEngine _engine;

        public RecommendationEngine(ComparisonEngine engine)
        {
            _engine = engine;
        }

        public string Generate(
            List<double> crossoverRoots,
            double? breakEvenA,
            double? breakEvenB,
            double volumeA,
            double volumeB)
        {
            var a = _engine.A;
            var b = _engine.B;

            var summary = _engine.SummaryAtVolumes(volumeA, volumeB);

            double profitA = summary.ProfitA;
            double profitB = summary.ProfitB;

            string betterName = profitA >= profitB ? a.Name : b.Name;
            string worseName = profitA >= profitB ? b.Name : a.Name;

            var lines = new List<string>();

            lines.Add(
                $"{a.Name} at volume {volumeA:N1}: profit ${profitA:N2}. " +
                $"{b.Name} at volume {volumeB:N1}: profit ${profitB:N2}."
            );

            lines.Add($"→ {betterName} shows higher profit at its expected volume.");

            if (breakEvenA != null)
                lines.Add($"{a.Name} breaks even at {breakEvenA.Value:N1} units.");
            else
                lines.Add($"{a.Name} does not break even in the modelled range.");

            if (breakEvenB != null)
                lines.Add($"{b.Name} breaks even at {breakEvenB.Value:N1} units.");
            else
                lines.Add($"{b.Name} does not break even in the modelled range.");

            double referenceVolume = Math.Max(volumeA, volumeB);

            if (crossoverRoots.Count > 0)
            {
                double r = crossoverRoots[0];

                if (r < referenceVolume)
                {
                    lines.Add(
                        $"The options cross at {r:N1} units — below expected volume. " +
                        $"{betterName} is superior at the current scale."
                    );
                }
                else
                {
                    lines.Add(
                        $"Options cross at {r:N1} units — above expected volume. " +
                        $"At lower volumes {worseName} may be safer."
                    );
                }
            }
            else
            {
                lines.Add($"{betterName} is dominant across the entire modelled range.");
            }

            var breakdownA = a.CostBreakdown(volumeA);
            if (breakdownA.Count > 0)
            {
                var top = breakdownA[0];
                lines.Add(
                    $"Biggest cost driver for {a.Name}: {top.Component} " +
                    $"(${top.Amount:N2}, {top.PercentOfTotal:F1}% of total cost)."
                );
            }

            var breakdownB = b.CostBreakdown(volumeB);
            if (breakdownB.Count > 0)
            {
                var top = breakdownB[0];
                lines.Add(
                    $"Biggest cost driver for {b.Name}: {top.Component} " +
                    $"(${top.Amount:N2}, {top.PercentOfTotal:F1}% of total cost)."
                );
            }

            lines.Add(
                $"Profit margins — {a.Name}: {summary.MarginA:F1}%  |  " +
                $"{b.Name}: {summary.MarginB:F1}%."
            );

            lines.Add("");
            lines.Add($"Recommendation: choose {betterName}.");

            return string.Join(Environment.NewLine, lines);
        }
    }

    // ============================================================
    // MATH PARSER
    // Supports:
    // x, numbers, +, -, *, /, ^, parentheses
    // sin, cos, tan, sqrt, log, ln, exp, abs
    // constants: pi, e
    // ============================================================

    public static class MathParser
    {
        public static Func<double, double> Compile(string expression)
        {
            if (string.IsNullOrWhiteSpace(expression))
                throw new ArgumentException("Expression cannot be empty.");

            return x =>
            {
                var parser = new ExpressionParser(expression, x);
                double value = parser.Parse();

                if (double.IsNaN(value) || double.IsInfinity(value))
                    throw new ArithmeticException("Expression evaluated to an invalid number.");

                return value;
            };
        }

        public static double Evaluate(string expression, double x)
        {
            return Compile(expression)(x);
        }

        private class ExpressionParser
        {
            private readonly string _text;
            private readonly double _x;
            private int _pos;

            public ExpressionParser(string text, double x)
            {
                _text = text;
                _x = x;
                _pos = 0;
            }

            public double Parse()
            {
                double result = ParseExpression();
                SkipWhitespace();

                if (_pos < _text.Length)
                    throw new FormatException($"Unexpected character '{_text[_pos]}' at position {_pos}.");

                return result;
            }

            private double ParseExpression()
            {
                double value = ParseTerm();

                while (true)
                {
                    SkipWhitespace();

                    if (Match('+'))
                        value += ParseTerm();
                    else if (Match('-'))
                        value -= ParseTerm();
                    else
                        break;
                }

                return value;
            }

            private double ParseTerm()
            {
                double value = ParsePower();

                while (true)
                {
                    SkipWhitespace();

                    if (Match('*'))
                        value *= ParsePower();
                    else if (Match('/'))
                    {
                        double divisor = ParsePower();

                        if (Math.Abs(divisor) < 1e-15)
                            throw new DivideByZeroException("Division by zero.");

                        value /= divisor;
                    }
                    else
                        break;
                }

                return value;
            }

            private double ParsePower()
            {
                double value = ParseUnary();

                SkipWhitespace();

                if (Match('^'))
                {
                    double exponent = ParsePower(); // right-associative
                    value = Math.Pow(value, exponent);
                }

                return value;
            }

            private double ParseUnary()
            {
                SkipWhitespace();

                if (Match('+'))
                    return ParseUnary();

                if (Match('-'))
                    return -ParseUnary();

                return ParsePrimary();
            }

            private double ParsePrimary()
            {
                SkipWhitespace();

                if (Match('('))
                {
                    double value = ParseExpression();

                    SkipWhitespace();

                    if (!Match(')'))
                        throw new FormatException("Missing closing parenthesis.");

                    return value;
                }

                if (CurrentIsLetter())
                {
                    string name = ParseIdentifier().ToLowerInvariant();

                    if (name == "x")
                        return _x;

                    if (name == "pi")
                        return Math.PI;

                    if (name == "e")
                        return Math.E;

                    SkipWhitespace();

                    if (!Match('('))
                        throw new FormatException($"Function '{name}' must be followed by parentheses.");

                    double arg = ParseExpression();

                    SkipWhitespace();

                    if (!Match(')'))
                        throw new FormatException($"Missing closing parenthesis after function '{name}'.");

                    return ApplyFunction(name, arg);
                }

                return ParseNumber();
            }

            private double ParseNumber()
            {
                SkipWhitespace();

                int start = _pos;
                bool hasDigit = false;

                while (_pos < _text.Length &&
                       (char.IsDigit(_text[_pos]) || _text[_pos] == '.'))
                {
                    if (char.IsDigit(_text[_pos]))
                        hasDigit = true;

                    _pos++;
                }

                if (_pos < _text.Length && (_text[_pos] == 'e' || _text[_pos] == 'E'))
                {
                    int expPos = _pos;
                    _pos++;

                    if (_pos < _text.Length && (_text[_pos] == '+' || _text[_pos] == '-'))
                        _pos++;

                    bool expHasDigit = false;

                    while (_pos < _text.Length && char.IsDigit(_text[_pos]))
                    {
                        expHasDigit = true;
                        _pos++;
                    }

                    if (!expHasDigit)
                        _pos = expPos;
                }

                if (!hasDigit)
                    throw new FormatException($"Expected number at position {start}.");

                string numberText = _text.Substring(start, _pos - start);

                if (!double.TryParse(
                        numberText,
                        NumberStyles.Float,
                        CultureInfo.InvariantCulture,
                        out double value))
                {
                    throw new FormatException($"Invalid number: {numberText}");
                }

                return value;
            }

            private string ParseIdentifier()
            {
                int start = _pos;

                while (_pos < _text.Length &&
                       (char.IsLetter(_text[_pos]) || _text[_pos] == '_'))
                {
                    _pos++;
                }

                return _text.Substring(start, _pos - start);
            }

            private double ApplyFunction(string name, double arg)
            {
                return name switch
                {
                    "sin" => Math.Sin(arg),
                    "cos" => Math.Cos(arg),
                    "tan" => Math.Tan(arg),
                    "sqrt" => Math.Sqrt(arg),
                    "log" => Math.Log10(arg),
                    "ln" => Math.Log(arg),
                    "exp" => Math.Exp(arg),
                    "abs" => Math.Abs(arg),
                    _ => throw new FormatException($"Unknown function: {name}")
                };
            }

            private bool Match(char c)
            {
                SkipWhitespace();

                if (_pos < _text.Length && _text[_pos] == c)
                {
                    _pos++;
                    return true;
                }

                return false;
            }

            private bool CurrentIsLetter()
            {
                SkipWhitespace();
                return _pos < _text.Length && char.IsLetter(_text[_pos]);
            }

            private void SkipWhitespace()
            {
                while (_pos < _text.Length && char.IsWhiteSpace(_text[_pos]))
                    _pos++;
            }
        }
    }
}
