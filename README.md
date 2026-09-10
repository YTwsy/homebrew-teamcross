# Team Cross Homebrew tap

选择一种安装方式；两种方式均提供 `teamcross` 命令。

## App 与命令行

```sh
brew install --cask YTwsy/teamcross/team-cross
```

## 独立命令行

```sh
brew install YTwsy/teamcross/teamcross
```

Formula 与 Cask 互斥。切换前退出 Team Cross 并通过原渠道卸载，协作数据与工作目录保留。首次打开与完整说明见 [Team Cross](https://github.com/YTwsy/Team-Cross/blob/v0.1.1/README.md#安装)。

从 Formula 切换到 App 时，使用 `brew uninstall --formula --force teamcross` 移除所有已安装的旧版本，再安装 Cask。
