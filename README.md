# Team Cross Homebrew tap

稳定版与 RC 使用独立通道；每种安装方式都提供 `teamcross` 命令，因此四种定义互斥，不能同时安装。

## 稳定版

App 与命令行：

```sh
brew install --cask YTwsy/teamcross/team-cross
```

独立命令行：

```sh
brew install YTwsy/teamcross/teamcross
```

## RC 候选版

App 与命令行：

```sh
brew install --cask YTwsy/teamcross/team-cross@rc
```

独立命令行：

```sh
brew install YTwsy/teamcross/teamcross-rc
```

RC 只在用户显式安装上述 RC 定义时生效，不会把稳定通道的普通 `brew upgrade` 自动切换到候选版。

切换渠道前退出 Team Cross，并通过原渠道卸载。Formula 使用 `brew uninstall --formula --force <名称>`，Cask 使用 `brew uninstall --cask <名称>`；协作数据和工作目录会保留。首次打开、未公证构建的系统提示与完整说明见 [Team Cross](https://github.com/YTwsy/Team-Cross#安装)。
