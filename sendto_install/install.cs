using System;
using System.IO;

class Installer
{
    static int Main(string[] args)
    {
        bool quiet = args.Length > 0 &&
            (args[0] == "--quiet" || args[0] == "/s" || args[0] == "-q");

        string src = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        if (!File.Exists(Path.Combine(src, "rename_dates.bat")))
        {
            string fallback = @"__SRC_ROOT__";
            if (Directory.Exists(fallback)) src = fallback;
        }
        if (!File.Exists(Path.Combine(src, "rename_dates.bat")))
        {
            Console.WriteLine("ERROR: Could not find the SendTo apps folder.");
            Console.WriteLine("Run install.exe from inside the sendto_install folder.");
            if (!quiet) Console.ReadKey();
            return 1;
        }

        string bin = Path.Combine(Environment.GetEnvironmentVariable("USERPROFILE"), "bin");
        string sendto = Environment.GetFolderPath(Environment.SpecialFolder.SendTo);
        Directory.CreateDirectory(bin);
        Directory.CreateDirectory(sendto);

        int ok = 0;
        int fail = 0;

        string[] apps =
        {
            "rename_dates.bat",
            "make_date_folders.bat",
            "move_jpg.bat",
            "make_pan.bat",
            "slideshow.bat",
            "random.bat"
        };
        string[] helpers =
        {
            "rename_dates.ps1",
            "make_date_folders.ps1",
            "make_pan.ps1"
        };
        string[] stale =
        {
            "organize_photos.bat",
            "organize_photos.ps1"
        };
        string[] dists =
        {
            "slideshow",
            "random"
        };

        Console.WriteLine("Installing simpleGraphy apps");
        Console.WriteLine("  from   : " + src);
        Console.WriteLine("  bin    : " + bin);
        Console.WriteLine("  SendTo : " + sendto);
        Console.WriteLine();

        foreach (string a in apps)
        {
            string s = Path.Combine(src, a);
            ok += Copy(s, Path.Combine(bin, a), ref fail);
            ok += Copy(s, Path.Combine(sendto, a), ref fail);
        }
        foreach (string p in helpers)
        {
            ok += Copy(Path.Combine(src, p), Path.Combine(bin, p), ref fail);
        }
        foreach (string d in dists)
        {
            string sdir = Path.Combine(src, d, "dist");
            if (!Directory.Exists(sdir)) sdir = Path.Combine(src, "..", d, "dist");
            string tdir = Path.Combine(bin, d);
            if (!Directory.Exists(sdir))
            {
                Console.WriteLine("MISS " + Path.GetFullPath(sdir) + "   (build it first: dotnet publish)");
                fail++;
                continue;
            }
            Directory.CreateDirectory(tdir);
            foreach (string f in Directory.GetFiles(sdir))
            {
                ok += Copy(f, Path.Combine(tdir, Path.GetFileName(f)), ref fail);
            }
        }

        foreach (string s in stale)
        {
            TryDelete(Path.Combine(bin, s));
            TryDelete(Path.Combine(sendto, s));
        }

        Console.WriteLine();
        Console.WriteLine("Done. Copied: " + ok + "   Failed: " + fail);
        Console.WriteLine("Right-click files/folders > Send to > make_pan.bat / slideshow.bat / random.bat ...");
        if (!quiet) Console.ReadKey();
        return fail == 0 ? 0 : 2;
    }

    static void TryDelete(string path)
    {
        try
        {
            if (File.Exists(path))
            {
                File.Delete(path);
                Console.WriteLine("DEL  " + path + "   (old name)");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("FAIL delete " + path + "   " + ex.Message);
        }
    }

    static int Copy(string srcFile, string dstFile, ref int fail)
    {
        try
        {
            if (!File.Exists(srcFile))
            {
                Console.WriteLine("MISS " + srcFile);
                fail++;
                return 0;
            }
            File.Copy(srcFile, dstFile, true);
            Console.WriteLine("OK   " + dstFile);
            return 1;
        }
        catch (Exception ex)
        {
            Console.WriteLine("FAIL " + dstFile + "   " + ex.Message);
            fail++;
            return 0;
        }
    }
}
