# 本次诉求

用户希望把 commit 消息语言约定写到 `docs/REPO_COLLAB_GUIDE.md` 的 `Git 与评审` 小节中。

## 主要改动

- 在 `docs/REPO_COLLAB_GUIDE.md` 的 `Git 与评审` 小节中补充 commit 语言规则。
- 约定 commit 标题首行默认使用英文。
- 约定 commit 正文和 git trailers 默认使用中文，除非用户明确要求其他语言。

## 设计动机

这条规则属于仓库级协作约定，放在 `REPO_COLLAB_GUIDE` 比放在 `AGENTS.md` 更符合当前仓库“AGENTS 只做导航、docs 承载正式规则”的结构。

## 关键受影响文件

- `docs/REPO_COLLAB_GUIDE.md`
