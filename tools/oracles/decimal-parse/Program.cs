// For each line "64 TEXT" or "32 TEXT" on stdin, prints the bits of (double)float.Parse(TEXT) or double.Parse(TEXT),
// as the reference parses float literals (TypeChecker.CheckFloatLiteral), in hexadecimal.
using System.Globalization;
string? line;
while ((line = Console.ReadLine()) is not null)
{
    var text = line[3..];
    var value = line.StartsWith("32", StringComparison.Ordinal)
        ? (double)float.Parse(text, NumberStyles.Float, CultureInfo.InvariantCulture)
        : double.Parse(text, NumberStyles.Float, CultureInfo.InvariantCulture);
    Console.WriteLine(BitConverter.DoubleToUInt64Bits(value).ToString("X16", CultureInfo.InvariantCulture));
}
