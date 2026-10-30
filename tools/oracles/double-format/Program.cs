// Prints double.ToString("R", InvariantCulture), as the reference's HIR dump does (HirPrinter.cs:203), for each
// hexadecimal bit pattern read from stdin, one per line. tools/oracles/gen_double_cases.py feeds it.
using System.Globalization;
string? line;
while ((line = Console.ReadLine()) is not null)
{
    var bits = ulong.Parse(line, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
    Console.WriteLine(BitConverter.UInt64BitsToDouble(bits).ToString("R", CultureInfo.InvariantCulture));
}
