class Teamcross < Formula
  desc "Continue a shared native Codex session on macOS"
  homepage "https://github.com/YTwsy/Team-Cross"
  url "https://github.com/YTwsy/Team-Cross/releases/download/v0.1.1/teamcross-0.1.1-darwin-arm64.tar.gz"
  version "0.1.1"
  sha256 "3f0eca5bea41afede97df4170b6181d0833c63d8792f2700068f348625cedad0"
  depends_on :macos => :sonoma
  depends_on arch: :arm64

  def install
    other_formula = HOMEBREW_CELLAR/"teamcross-rc"
    if Dir.glob((other_formula/"*/INSTALL_RECEIPT.json").to_s).any?
      odie "请先运行 brew uninstall --formula --force teamcross-rc，再安装此 CLI 通道。协作数据会保留。"
    end

    # Formula conflicts do not cover Casks, so check both App channels.
    installed_cask = ["team-cross", "team-cross@rc"].find do |token|
      (HOMEBREW_PREFIX/"Caskroom/#{token}/.metadata/INSTALL_RECEIPT.json").file?
    end
    if installed_cask
      odie "请先运行 brew uninstall --cask #{installed_cask}，再安装 CLI。协作数据会保留。"
    end
    bin.install "teamcross"
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/teamcross version")
    assert_match "commit", shell_output("#{bin}/teamcross version --json")
  end
end
