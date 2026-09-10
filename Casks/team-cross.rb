cask "team-cross" do
  version "0.1.1"
  sha256 "26edecf9de23bc05b12ee51b57e68f837044440783a45fa8f03055cdb1c9e31d"
  url "https://github.com/YTwsy/Team-Cross/releases/download/v0.1.1/Team-Cross-0.1.1-arm64.dmg"
  name "Team Cross"
  desc "Menu bar companion for native Codex collaboration"
  homepage "https://github.com/YTwsy/Team-Cross"
  depends_on macos: :sonoma
  depends_on arch: :arm64
  app "Team Cross.app"
  binary "#{appdir}/Team Cross.app/Contents/Resources/teamcross", target: "teamcross"

  preflight do
    if Dir.glob((HOMEBREW_CELLAR/"teamcross/*/INSTALL_RECEIPT.json").to_s).any?
      # A normal exception lets Homebrew roll back its staged installation.
      raise "请先运行 brew uninstall --formula --force teamcross，移除所有旧版本后再安装 App。协作数据会保留。"
    end
  end

  caveats <<~EOS
    安装后可打开 Team Cross.app，或在终端运行 teamcross。
    如果首次打开受到系统提示，请按发布页的安装说明在“隐私与安全性”中允许打开。
    升级或卸载前请退出 Team Cross；协作数据和工作目录会保留。
  EOS
end
