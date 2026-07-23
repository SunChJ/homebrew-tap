cask "gloss" do
  version "0.8.1"

  on_arm do
    sha256 "19fa355023180a3d364b7a146d583daed4127c4b368c3dbbea7de42f8e321a24"

    url "https://github.com/SunChJ/gloss-releases/releases/download/v0.8.1/Gloss-macos-arm64.zip"
  end
  on_intel do
    sha256 "568d2293b77fc150e986b7ad33ee3bea4a8034650af6464a7d169142f1231e44"

    url "https://github.com/SunChJ/gloss-releases/releases/download/v0.8.1/Gloss-macos-x86_64.zip"
  end

  name "Gloss"
  desc "Context-aware text and document translation"
  homepage "https://github.com/SunChJ/gloss-releases"

  depends_on macos: :sonoma

  app "Gloss.app"

  postflight do
    app_path = "#{appdir}/Gloss.app"
    extension_path = "#{app_path}/Contents/PlugIns/Gloss Extension.appex"
    entitlement_paths = [extension_path, app_path]
    entitlements_before = entitlement_paths.map do |code_path|
      system_command("/usr/bin/codesign",
                     args:         ["--display", "--entitlements", "-", code_path],
                     sudo:         false,
                     must_succeed: true,
                     print_stderr: false).stdout
    end
    code_paths = [
      extension_path,
      "#{app_path}/Contents/Helpers/gloss-codex-app-server",
      "#{app_path}/Contents/Helpers/gloss-cli",
      app_path,
    ]
    code_paths.each do |code_path|
      system_command "/usr/bin/codesign",
                     args:         [
                       "--force",
                       "--sign",
                       "-",
                       "--preserve-metadata=identifier,entitlements,requirements,flags,runtime",
                       code_path,
                     ],
                     sudo:         false,
                     must_succeed: true
    end
    entitlements_after = entitlement_paths.map do |code_path|
      system_command("/usr/bin/codesign",
                     args:         ["--display", "--entitlements", "-", code_path],
                     sudo:         false,
                     must_succeed: true,
                     print_stderr: false).stdout
    end
    raise "Gloss code-signing entitlements changed during installation" if entitlements_after != entitlements_before

    system_command "/usr/bin/xattr",
                   args:         ["-dr", "com.apple.quarantine", app_path],
                   sudo:         false,
                   must_succeed: true
    remaining_attributes = system_command "/usr/bin/xattr",
                                          args:         ["-lr", app_path],
                                          sudo:         false,
                                          must_succeed: true,
                                          print_stderr: false
    if remaining_attributes.stdout.include?("com.apple.quarantine")
      raise "Gloss quarantine attribute remains after installation"
    end

    system_command "/usr/bin/codesign",
                   args:         ["--verify", "--deep", "--strict", app_path],
                   sudo:         false,
                   must_succeed: true
  end

  uninstall quit: "com.samsoncj.gloss"

  zap trash: [
    "~/Library/Application Support/Gloss",
    "~/Library/Caches/Gloss",
    "~/Library/Logs/Gloss",
    "~/Library/Preferences/com.samsoncj.gloss.plist",
  ]

  caveats <<~EOS
    Gloss uses an ad-hoc code signature and is not Apple-notarized. This custom
    tap re-signs the installed app and removes its quarantine attribute.
  EOS
end
