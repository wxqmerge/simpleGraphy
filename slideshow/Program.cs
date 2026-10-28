using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace Slideshow;

static class Program
{
    static List<string> images = new();
    static int index = 0;
    static System.Windows.Forms.Timer? timer;
    static int intervalMs = 5000;
    static bool isPlaying = true;
    static List<string> infoParts = new();
    static Form? form;
    static PictureBox? pic;
    static Image? currentImage;
    static int screenIdx = 0;

    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();

        string dir = args.Length > 0 ? args[0].Trim().Trim('"') : PickFolder() ?? "";
        if (string.IsNullOrEmpty(dir)) Environment.Exit(0);
        if (args.Length > 1 && int.TryParse(args[1], out int secs) && secs > 0)
        {
            long ms = (long)secs * 1000;
            if (ms <= int.MaxValue) intervalMs = (int)ms;
        }

        if (!Directory.Exists(dir))
        {
            MessageBox.Show($"Directory not found:\n{dir}", "Slideshow", MessageBoxButtons.OK, MessageBoxIcon.Error);
            Environment.Exit(1);
        }

        string[] exts = { "*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.tiff", "*.tif" };
        CollectImages(dir, exts, images);

        if (images.Count == 0)
        {
            MessageBox.Show($"No images found in:\n{dir}", "Slideshow", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            Environment.Exit(1);
        }

        images.Sort(StringComparer.OrdinalIgnoreCase);

        form = new Form
        {
            Text = "Slideshow",
            FormBorderStyle = FormBorderStyle.None,
            BackColor = Color.Black,
            KeyPreview = true,
            StartPosition = FormStartPosition.Manual,
        };
        ApplyScreen();

        pic = new PictureBox
        {
            Dock = DockStyle.Fill,
            SizeMode = PictureBoxSizeMode.Zoom,
            BackColor = Color.Black,
        };
        form.Controls.Add(pic);

        pic.Paint += Pic_Paint;

        timer = new System.Windows.Forms.Timer { Interval = intervalMs };
        timer.Tick += (_, _) =>
        {
            if (isPlaying)
                Advance(+1);
        };
        timer.Start();

        form.KeyDown += (_, e) =>
        {
            switch (e.KeyCode)
            {
                case Keys.Escape:
                    Environment.Exit(0);
                    break;
                case Keys.Space:
                case Keys.Enter:
                    if (isPlaying)
                        isPlaying = false;
                    else
                    {
                        isPlaying = true;
                        Advance(+1);
                    }
                    break;
                case Keys.Left:
                    isPlaying = false;
                    Advance(-1);
                    break;
                case Keys.Right:
                    isPlaying = false;
                    Advance(+1);
                    break;
                case Keys.S:
                    screenIdx = (screenIdx + 1) % Screen.AllScreens.Length;
                    ApplyScreen();
                    break;
            }
        };

        pic.MouseClick += (_, e) =>
        {
            isPlaying = false;
            try { Clipboard.SetText(images[index]); } catch { }
            if (e.Button == MouseButtons.Left) Advance(+1);
            else if (e.Button == MouseButtons.Right) Advance(-1);
        };

        Advance(0);
        Application.Run(form);
        Environment.Exit(0);
    }

    static void Pic_Paint(object? sender, PaintEventArgs e)
    {
        if (pic == null) return;
        var g = e.Graphics;

        int cw = pic.ClientSize.Width;
        int ch = pic.ClientSize.Height;
        if (currentImage != null && cw > 0 && ch > 0)
        {
            float scale = Math.Min((float)cw / currentImage.Width, (float)ch / currentImage.Height);
            int iw = (int)(currentImage.Width * scale);
            int ih = (int)(currentImage.Height * scale);
            g.DrawImage(currentImage, (cw - iw) / 2, (ch - ih) / 2, iw, ih);
        }

        string status = isPlaying ? "" : "  [PAUSED]";

        var lines = new List<string>
        {
            $"{index + 1}/{images.Count}",
        };
        lines.AddRange(WrapPath(images[index]));
        lines.AddRange(infoParts);
        if (!string.IsNullOrEmpty(status))
            lines.Add(status.Trim());

        var font = new Font("Segoe UI", 12f);
        int h = (int)font.Height;
        int pad = 10;

        var fg = new SolidBrush(Color.White);
        for (int i = 0; i < lines.Count; i++)
            g.DrawString(lines[i], font, fg, pad, pad + i * h);

        font.Dispose();
        fg.Dispose();
    }

    static void ApplyScreen()
    {
        form!.Bounds = Screen.AllScreens[screenIdx % Screen.AllScreens.Length].Bounds;
    }

    // Recurse directories, skipping ones we cannot read; collect files matching exts.
    static void CollectImages(string dir, string[] exts, List<string> into)
    {
        foreach (var ext in exts)
        {
            try { into.AddRange(Directory.GetFiles(dir, ext)); }
            catch (Exception ex) when (ex is UnauthorizedAccessException || ex is PathTooLongException || ex is IOException) { }
        }

        string[] subdirs;
        try { subdirs = Directory.GetDirectories(dir); }
        catch (Exception ex) when (ex is UnauthorizedAccessException || ex is PathTooLongException || ex is IOException) { return; }
        foreach (var sd in subdirs)
            CollectImages(sd, exts, into);
    }

    static void Advance(int dir)
    {
        index = (index + dir + images.Count) % images.Count;
        ShowImage();
    }

    static void ShowImage()
    {
        string path = images[index];
        string name = Path.GetFileName(path);
        try
        {
            // Image.FromStream needs the stream alive for the image's lifetime;
            // read bytes first and make a pixel copy that survives disposal.
            byte[] data = File.ReadAllBytes(path);
            using var ms = new MemoryStream(data);
            using var img = Image.FromStream(ms);
            img.RotateFlip(GetRotateFlip(img));

            infoParts = BuildInfo(img, path);
            currentImage?.Dispose();
            currentImage = new Bitmap(img);
        }
        catch
        {
            infoParts = new List<string> { $"Cannot load: {name}" };
            currentImage?.Dispose();
            currentImage = null;
        }
        pic?.Invalidate();
    }

    static List<string> BuildInfo(Image img, string path)
    {
        var parts = new List<string>();
        parts.Add($"{img.Width}x{img.Height}");

        var fi = new FileInfo(path);
        parts.Add(HumanSize(fi.Length));

        string? camera = null;
        string? focal = null;

        foreach (var p in img.PropertyItems)
        {
            switch (p.Id)
            {
                case 0x010F:
                    camera = DecodeString(p);
                    break;
                case 0x0110:
                    camera = camera != null ? camera + " " + DecodeString(p) : DecodeString(p);
                    break;
                case 0xA22B:
                    if (p.Value != null && p.Value.Length >= 2)
                        focal = $"{BitConverter.ToInt16(p.Value, 0)}mm (35mm equiv)";
                    break;
                case 0x920A:
                    if (p.Value != null && p.Value.Length >= 8)
                    {
                        int num = BitConverter.ToInt32(p.Value, 0);
                        int den = BitConverter.ToInt32(p.Value, 4);
                        if (den != 0)
                            focal = $"{num / (double)den:0.#}mm";
                    }
                    break;
            }
        }

        if (camera != null && camera.Trim().Length > 0)
            parts.Add(camera.Trim());
        if (focal != null)
            parts.Add(focal);

        return parts;
    }

    static string? PickFolder()
    {
        using var dlg = new FolderBrowserDialog
        {
            Description = "Select photo directory",
            UseDescriptionForTitle = true,
            ShowNewFolderButton = false,
            AutoUpgradeEnabled = true,
        };
        return dlg.ShowDialog() == DialogResult.OK ? dlg.SelectedPath : null;
    }

    static RotateFlipType GetRotateFlip(Image img)
    {
        foreach (var p in img.PropertyItems)
        {
            if (p.Id == 0x0112 && p.Value != null && p.Value.Length >= 2)
            {
                int o = BitConverter.ToInt16(p.Value, 0);
                return o switch
                {
                    2 => RotateFlipType.RotateNoneFlipX,
                    3 => RotateFlipType.Rotate180FlipNone,
                    4 => RotateFlipType.RotateNoneFlipY,
                    5 => RotateFlipType.Rotate90FlipX,
                    6 => RotateFlipType.Rotate90FlipNone,
                    7 => RotateFlipType.Rotate270FlipX,
                    8 => RotateFlipType.Rotate270FlipNone,
                    _ => RotateFlipType.RotateNoneFlipNone,
                };
            }
        }
        return RotateFlipType.RotateNoneFlipNone;
    }

    static string DecodeString(PropertyItem p)
    {
        if (p.Value == null) return "";
        var sb = new StringBuilder();
        foreach (byte b in p.Value)
            if (b != 0) sb.Append((char)b);
        return sb.ToString().Trim();
    }

    static List<string> WrapPath(string path)
    {
        var segs = path.Split(new[] { '\\', '/' }, StringSplitOptions.None);
        int n = segs.Length;
        if (n == 0) return new List<string> { path };

        int[] dp = new int[n + 1];
        int[] next = new int[n + 1];
        dp[n] = 0;
        for (int i = n - 1; i >= 0; i--)
        {
            dp[i] = int.MaxValue;
            int len = 0;
            for (int j = i; j < n; j++)
            {
                len = j == i ? segs[j].Length : len + 1 + segs[j].Length;
                int lineMax = Math.Max(len, dp[j + 1]);
                if (lineMax < dp[i])
                {
                    dp[i] = lineMax;
                    next[i] = j;
                }
            }
        }

        var lines = new List<string>();
        int start = 0;
        while (start < n)
        {
            int j = next[start];
            var sb = new StringBuilder();
            for (int k = start; k <= j; k++)
            {
                if (k > start) sb.Append('/');
                sb.Append(segs[k]);
            }
            lines.Add(sb.ToString());
            start = j + 1;
        }
        return lines;
    }

    static string HumanSize(long bytes)
    {
        if (bytes >= 1073741824) return $"{bytes / 1073741824.0:0.0} GB";
        if (bytes >= 1048576) return $"{bytes / 1048576.0:0.0} MB";
        if (bytes >= 1024) return $"{bytes / 1024:0} KB";
        return $"{bytes} B";
    }
}
