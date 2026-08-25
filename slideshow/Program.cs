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

    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();

        string dir = args.Length > 0 ? args[0].Trim().Trim('"') : PickFolder() ?? "";
        if (string.IsNullOrEmpty(dir)) Environment.Exit(0);
        if (args.Length > 1 && int.TryParse(args[1], out int secs))
            intervalMs = secs * 1000;

        if (!Directory.Exists(dir))
        {
            MessageBox.Show($"Directory not found:\n{dir}", "Slideshow", MessageBoxButtons.OK, MessageBoxIcon.Error);
            Environment.Exit(1);
        }

        string[] exts = { "*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.tiff", "*.tif" };
        foreach (var ext in exts)
            images.AddRange(Directory.GetFiles(dir, ext, SearchOption.AllDirectories));

        if (images.Count == 0)
        {
            MessageBox.Show($"No images found in:\n{dir}", "Slideshow", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            Environment.Exit(1);
        }

        images.Sort(StringComparer.OrdinalIgnoreCase);

        var screen = Screen.PrimaryScreen.Bounds;
        form = new Form
        {
            Text = "Slideshow",
            FormBorderStyle = FormBorderStyle.None,
            BackColor = Color.Black,
            KeyPreview = true,
            StartPosition = FormStartPosition.Manual,
            Location = new Point(screen.Left, screen.Top),
            Size = new Size(screen.Width, screen.Height),
        };

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
            }
        };

        form.MouseClick += (_, e) =>
        {
            isPlaying = false;
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

        string name = Path.GetFileName(images[index]);
        string status = isPlaying ? "" : "  [PAUSED]";

        var lines = new List<string>
        {
            $"{index + 1}/{images.Count}",
            name,
        };
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
            pic!.Image?.Dispose();
            using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
            using var img = Image.FromStream(fs);

            infoParts = BuildInfo(img, path);
            pic.Image = (Image)img.Clone();
        }
        catch
        {
            infoParts = new List<string> { $"Cannot load: {name}" };
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

    static string DecodeString(PropertyItem p)
    {
        if (p.Value == null) return "";
        var sb = new StringBuilder();
        foreach (byte b in p.Value)
            if (b != 0) sb.Append((char)b);
        return sb.ToString().Trim();
    }

    static string HumanSize(long bytes)
    {
        if (bytes >= 1073741824) return $"{bytes / 1073741824.0:0.0} GB";
        if (bytes >= 1048576) return $"{bytes / 1048576.0:0.0} MB";
        if (bytes >= 1024) return $"{bytes / 1024:0} KB";
        return $"{bytes} B";
    }
}
