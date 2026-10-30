// Prints the reference lexer's output in ceesafec's `parse --dump-tokens` format (src/syntax/token_dump.nova). Files
// are read as novac's parse command reads them (File.ReadAllText, SourceText.SourcePath), with one SymbolTable for all.
using System.Text;
using Nova.Compiler.Diagnostics;
using Nova.Compiler.Syntax;

var output = new StringBuilder();
var symbols = new SymbolTable();
var diagnostics = new DiagnosticBag();
foreach (var file in args)
{
    var source = new SourceText(SourceText.SourcePath(file, Environment.CurrentDirectory), File.ReadAllText(file));
    var lexed = Lexer.Lex(source, symbols, diagnostics);
    output.Append("file ").Append(source.Path).Append('\n');
    foreach (var t in lexed.Tokens)
    {
        output.Append(t.Kind).Append(' ').Append(t.Span.Start).Append(' ').Append(t.Span.End);
        switch (t.Kind)
        {
            case TokenKind.Identifier:
                output.Append(' ').Append(t.Data).Append(' ').Append(symbols.GetName(new Symbol(t.Data)));
                break;
            case TokenKind.IntLiteral:
                output.Append(' ').Append(lexed.Ints[t.Data].Value).Append(' ').Append(lexed.Ints[t.Data].Suffix);
                break;
            case TokenKind.FloatLiteral:
                output.Append(' ').Append(lexed.Floats[t.Data].Digits).Append(' ').Append(lexed.Floats[t.Data].Suffix);
                break;
            case TokenKind.StringLiteral:
                output.Append(' ').Append(Convert.ToHexString(Encoding.UTF8.GetBytes(lexed.Strings[t.Data])));
                break;
            case TokenKind.CharLiteral:
                output.Append(' ').Append(lexed.Chars[t.Data]);
                break;
        }
        output.Append('\n');
    }
    foreach (var (token, text) in lexed.Docs.OrderBy(d => d.Key))
    {
        output.Append("doc ").Append(token).Append(' ').Append(Convert.ToHexString(Encoding.UTF8.GetBytes(text))).Append('\n');
    }
    foreach (var c in lexed.Comments)
    {
        output.Append("comment ").Append(c.Start).Append(' ').Append(c.End).Append('\n');
    }
    foreach (var d in diagnostics.Items.Where(d => d.Source == source))
    {
        output.Append("diagnostic ").Append(d.Code).Append(' ').Append(d.Span.Start).Append(' ').Append(d.Span.End)
            .Append(' ').Append(d.Message).Append('\n');
    }
}
using var stdout = Console.OpenStandardOutput();
var bytes = new UTF8Encoding(false).GetBytes(output.ToString());
stdout.Write(bytes);
