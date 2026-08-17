using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json.Nodes;

const string ServerName = "arknights-continuous-input";
const string ServerVersion = "0.1.0";

if (args.Contains("--self-test", StringComparer.Ordinal))
{
    DragRequest.Parse(JsonNode.Parse("""
        {"points":[{"x":10,"y":20},{"x":30,"y":40,"dwell_ms":100}],"segment_ms":180,"step_ms":8}
        """)!.AsObject());
    Console.WriteLine("self-test: ok");
    return;
}

while (await Console.In.ReadLineAsync() is { } line)
{
    if (string.IsNullOrWhiteSpace(line)) continue;

    JsonObject? message = null;
    try
    {
        message = JsonNode.Parse(line)?.AsObject();
        if (message is null) continue;
        var method = message["method"]?.GetValue<string>();
        var id = message["id"]?.DeepClone();
        if (id is null) continue;

        var result = method switch
        {
            "initialize" => Initialize(message),
            "ping" => new JsonObject(),
            "tools/list" => ToolList(),
            "tools/call" => CallTool(message),
            _ => throw new RpcException(-32601, $"Method not found: {method}"),
        };
        WriteResponse(id, result);
    }
    catch (Exception error)
    {
        var id = message?["id"]?.DeepClone();
        if (id is null) continue;
        var rpc = error as RpcException;
        WriteError(id, rpc?.Code ?? -32000, error.Message);
    }
}

static JsonObject Initialize(JsonObject request)
{
    var requested = request["params"]?["protocolVersion"]?.GetValue<string>();
    return new JsonObject
    {
        ["protocolVersion"] = requested ?? "2024-11-05",
        ["capabilities"] = new JsonObject { ["tools"] = new JsonObject { ["listChanged"] = false } },
        ["serverInfo"] = new JsonObject { ["name"] = ServerName, ["version"] = ServerVersion },
    };
}

static JsonObject ToolList() => new()
{
    ["tools"] = new JsonArray
    {
        new JsonObject
        {
            ["name"] = "arknights_continuous_drag",
            ["title"] = "Arknights continuous drag",
            ["description"] = "Hold the physical left mouse button while moving through 2-8 window-relative points in the unique visible Arknights PC window.",
            ["inputSchema"] = new JsonObject
            {
                ["type"] = "object",
                ["properties"] = new JsonObject
                {
                    ["points"] = new JsonObject
                    {
                        ["type"] = "array",
                        ["minItems"] = 2,
                        ["maxItems"] = 8,
                        ["items"] = new JsonObject
                        {
                            ["type"] = "object",
                            ["properties"] = new JsonObject
                            {
                                ["x"] = new JsonObject { ["type"] = "integer" },
                                ["y"] = new JsonObject { ["type"] = "integer" },
                                ["dwell_ms"] = new JsonObject { ["type"] = "integer", ["minimum"] = 0, ["maximum"] = 1000 },
                            },
                            ["required"] = new JsonArray("x", "y"),
                            ["additionalProperties"] = false,
                        },
                    },
                    ["segment_ms"] = new JsonObject { ["type"] = "integer", ["minimum"] = 50, ["maximum"] = 2000, ["default"] = 180 },
                    ["step_ms"] = new JsonObject { ["type"] = "integer", ["minimum"] = 4, ["maximum"] = 50, ["default"] = 8 },
                },
                ["required"] = new JsonArray("points"),
                ["additionalProperties"] = false,
            },
            ["annotations"] = new JsonObject { ["destructiveHint"] = false, ["openWorldHint"] = false },
        },
        new JsonObject
        {
            ["name"] = "arknights_release_mouse",
            ["title"] = "Release left mouse button",
            ["description"] = "Send a left-button-up event as an emergency recovery action.",
            ["inputSchema"] = new JsonObject { ["type"] = "object", ["additionalProperties"] = false },
            ["annotations"] = new JsonObject { ["destructiveHint"] = false, ["openWorldHint"] = false },
        },
    },
};

static JsonObject CallTool(JsonObject request)
{
    var parameters = request["params"]?.AsObject() ?? throw new RpcException(-32602, "Missing params");
    var name = parameters["name"]?.GetValue<string>() ?? throw new RpcException(-32602, "Missing tool name");
    var arguments = parameters["arguments"]?.AsObject() ?? new JsonObject();

    return name switch
    {
        "arknights_continuous_drag" => ToolResult(ArknightsInput.Drag(DragRequest.Parse(arguments))),
        "arknights_release_mouse" => ToolResult(ArknightsInput.Release()),
        _ => throw new RpcException(-32602, $"Unknown tool: {name}"),
    };
}

static JsonObject ToolResult(string text) => new()
{
    ["content"] = new JsonArray(new JsonObject { ["type"] = "text", ["text"] = text }),
};

static void WriteResponse(JsonNode id, JsonObject result) => Write(new JsonObject
{
    ["jsonrpc"] = "2.0",
    ["id"] = id,
    ["result"] = result,
});

static void WriteError(JsonNode id, int code, string message) => Write(new JsonObject
{
    ["jsonrpc"] = "2.0",
    ["id"] = id,
    ["error"] = new JsonObject { ["code"] = code, ["message"] = message },
});

static void Write(JsonObject message)
{
    Console.Out.WriteLine(message.ToJsonString());
    Console.Out.Flush();
}

sealed class RpcException(int code, string message) : Exception(message)
{
    public int Code { get; } = code;
}

sealed record DragPoint(int X, int Y, int DwellMs);

sealed record DragRequest(IReadOnlyList<DragPoint> Points, int SegmentMs, int StepMs)
{
    public static DragRequest Parse(JsonObject input)
    {
        var nodes = input["points"]?.AsArray() ?? throw new RpcException(-32602, "points is required");
        if (nodes.Count is < 2 or > 8) throw new RpcException(-32602, "points must contain 2-8 items");

        var points = nodes.Select((node, index) =>
        {
            var point = node?.AsObject() ?? throw new RpcException(-32602, $"points[{index}] must be an object");
            var x = RequiredInt(point, "x");
            var y = RequiredInt(point, "y");
            var dwell = OptionalInt(point, "dwell_ms", 0, 0, 1000);
            return new DragPoint(x, y, dwell);
        }).ToArray();

        return new DragRequest(
            points,
            OptionalInt(input, "segment_ms", 180, 50, 2000),
            OptionalInt(input, "step_ms", 8, 4, 50));
    }

    private static int RequiredInt(JsonObject input, string name) =>
        input[name]?.GetValue<int>() ?? throw new RpcException(-32602, $"{name} is required");

    private static int OptionalInt(JsonObject input, string name, int fallback, int minimum, int maximum)
    {
        var value = input[name]?.GetValue<int>() ?? fallback;
        if (value < minimum || value > maximum) throw new RpcException(-32602, $"{name} must be between {minimum} and {maximum}");
        return value;
    }
}

static class ArknightsInput
{
    private const uint LeftDown = 0x0002;
    private const uint LeftUp = 0x0004;
    private const int EscapeKey = 0x1B;

    public static string Drag(DragRequest request)
    {
        var window = FindUniqueWindow();
        ValidatePoints(window, request.Points);
        Focus(window.Handle);

        var first = ToScreen(window, request.Points[0]);
        if (!SetCursorPos(first.X, first.Y)) throw new InvalidOperationException("SetCursorPos failed");
        Thread.Sleep(request.Points[0].DwellMs);

        var pressed = false;
        try
        {
            SendMouse(LeftDown);
            pressed = true;

            for (var i = 1; i < request.Points.Count; i++)
            {
                EnsureUninterrupted(window.Handle);
                Move(window, request.Points[i - 1], request.Points[i], request.SegmentMs, request.StepMs);
                Thread.Sleep(request.Points[i].DwellMs);
            }

            return $"Dragged through {request.Points.Count} points in Arknights.exe.";
        }
        finally
        {
            if (pressed) SendMouse(LeftUp);
        }
    }

    public static string Release()
    {
        SendMouse(LeftUp);
        return "Left mouse button released.";
    }

    private static void Move(TargetWindow window, DragPoint from, DragPoint to, int durationMs, int stepMs)
    {
        var steps = Math.Max(1, durationMs / stepMs);
        for (var step = 1; step <= steps; step++)
        {
            EnsureUninterrupted(window.Handle);
            var t = step / (double)steps;
            var eased = t * t * (3 - 2 * t);
            var point = new DragPoint(
                (int)Math.Round(from.X + (to.X - from.X) * eased),
                (int)Math.Round(from.Y + (to.Y - from.Y) * eased),
                0);
            var screen = ToScreen(window, point);
            if (!SetCursorPos(screen.X, screen.Y)) throw new InvalidOperationException("SetCursorPos failed");
            Thread.Sleep(stepMs);
        }
    }

    private static void EnsureUninterrupted(nint handle)
    {
        if (GetForegroundWindow() != handle) throw new InvalidOperationException("Arknights lost foreground focus; drag aborted");
        if ((GetAsyncKeyState(EscapeKey) & 0x8000) != 0) throw new InvalidOperationException("Escape pressed; drag aborted");
    }

    private static void ValidatePoints(TargetWindow window, IReadOnlyList<DragPoint> points)
    {
        foreach (var point in points)
        {
            if (point.X < 0 || point.X >= window.Width || point.Y < 0 || point.Y >= window.Height)
                throw new RpcException(-32602, $"Point ({point.X},{point.Y}) is outside the Arknights window ({window.Width}x{window.Height})");
        }
    }

    private static TargetWindow FindUniqueWindow()
    {
        var matches = new List<TargetWindow>();
        EnumWindows((handle, _) =>
        {
            if (!IsWindowVisible(handle)) return true;
            var length = GetWindowTextLength(handle);
            if (length == 0) return true;

            var title = new StringBuilder(length + 1);
            GetWindowText(handle, title, title.Capacity);
            if (!string.Equals(title.ToString(), "明日方舟", StringComparison.Ordinal)) return true;

            GetWindowThreadProcessId(handle, out var processId);
            try
            {
                using var process = Process.GetProcessById((int)processId);
                if (!string.Equals(Path.GetFileName(process.MainModule?.FileName), "Arknights.exe", StringComparison.OrdinalIgnoreCase)) return true;
                if (DwmGetWindowAttribute(handle, 9, out var rect, Marshal.SizeOf<RECT>()) != 0 && !GetWindowRect(handle, out rect)) return true;
                var scale = Math.Max(1, GetDpiForWindow(handle)) / 96d;
                matches.Add(new TargetWindow(
                    handle,
                    rect.Left,
                    rect.Top,
                    (int)Math.Round((rect.Right - rect.Left) / scale),
                    (int)Math.Round((rect.Bottom - rect.Top) / scale),
                    scale));
            }
            catch
            {
                // Ignore inaccessible non-target processes with the same title.
            }
            return true;
        }, 0);

        return matches.Count == 1
            ? matches[0]
            : throw new InvalidOperationException($"Expected exactly one visible Arknights.exe window titled 明日方舟; found {matches.Count}");
    }

    private static void Focus(nint handle)
    {
        if (GetForegroundWindow() != handle)
        {
            SetForegroundWindow(handle);
            Thread.Sleep(150);
        }
        if (GetForegroundWindow() != handle) throw new InvalidOperationException("Could not focus the Arknights window");
    }

    private static (int X, int Y) ToScreen(TargetWindow window, DragPoint point) =>
        (window.Left + (int)Math.Round(point.X * window.Scale), window.Top + (int)Math.Round(point.Y * window.Scale));

    private static void SendMouse(uint flags)
    {
        var input = new INPUT
        {
            Type = 0,
            Mouse = new MOUSEINPUT { Flags = flags },
        };
        if (SendInput(1, [input], Marshal.SizeOf<INPUT>()) != 1) throw new InvalidOperationException($"SendInput failed: {Marshal.GetLastWin32Error()}");
    }

    private sealed record TargetWindow(nint Handle, int Left, int Top, int Width, int Height, double Scale);

    private delegate bool EnumWindowsProc(nint handle, nint parameter);

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT { public int Left, Top, Right, Bottom; }

    [StructLayout(LayoutKind.Sequential)]
    private struct INPUT { public uint Type; public MOUSEINPUT Mouse; }

    [StructLayout(LayoutKind.Sequential)]
    private struct MOUSEINPUT
    {
        public int Dx;
        public int Dy;
        public uint MouseData;
        public uint Flags;
        public uint Time;
        public nint ExtraInfo;
    }

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumWindows(EnumWindowsProc callback, nint parameter);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(nint handle);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(nint handle, StringBuilder text, int maximum);

    [DllImport("user32.dll")]
    private static extern int GetWindowTextLength(nint handle);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint handle, out uint processId);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetWindowRect(nint handle, out RECT rect);

    [DllImport("dwmapi.dll")]
    private static extern int DwmGetWindowAttribute(nint handle, int attribute, out RECT value, int size);

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern uint GetDpiForWindow(nint handle);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetForegroundWindow(nint handle);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetCursorPos(int x, int y);

    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int virtualKey);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint count, INPUT[] inputs, int size);
}
