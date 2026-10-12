"""将 计算过程文档.md 转换为带精美样式的独立 HTML"""
import markdown, re, os

BASE = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.path.join(BASE, '计算过程文档.md')
HTML_PATH = os.path.join(BASE, '计算过程文档.html')

with open(MD_PATH, 'r', encoding='utf-8') as f:
    md = f.read()

body = markdown.markdown(
    md,
    extensions=['tables', 'fenced_code', 'toc', 'codehilite', 'admonition', 'sane_lists'],
    extension_configs={
        'codehilite': {'css_class': 'highlight'},
        'toc': {'title': '目录', 'permalink': True, 'anchorlink': True},
    }
)

# 提取 TOC
toc_match = re.search(r'<div class="toc">(.+?)</div>', body, re.DOTALL)
toc_html = toc_match.group(1) if toc_match else ''
body_main = re.sub(r'<div class="toc">.+?</div>', '', body, flags=re.DOTALL)

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KELKCalCv 计算过程文档</title>
<style>
:root{
  --primary:#2563eb; --primary-dark:#1d4ed8; --accent:#0ea5e9;
  --bg:#f8fafc; --card:#ffffff; --text:#1e293b; --text-2:#475569; --text-3:#94a3b8;
  --border:#e2e8f0; --border-2:#cbd5e1; --success:#16a34a; --warn:#d97706; --danger:#dc2626;
  --code-bg:#0f172a; --code-text:#e2e8f0;
  --shadow:0 1px 3px rgba(0,0,0,.07), 0 1px 2px rgba(0,0,0,.04);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei','Helvetica Neue',sans-serif;
  background:var(--bg); color:var(--text); margin:0; line-height:1.75; font-size:14.5px;
}
.layout{display:grid; grid-template-columns:270px 1fr; min-height:100vh}

/* 侧边栏目录 */
.sidebar{
  background:linear-gradient(180deg,#1e293b 0%,#0f172a 100%); color:#cbd5e1;
  padding:28px 0; position:sticky; top:0; height:100vh; overflow-y:auto;
  border-right:1px solid #0f172a;
}
.sidebar::-webkit-scrollbar{width:6px}
.sidebar::-webkit-scrollbar-thumb{background:#334155; border-radius:3px}
.sidebar::-webkit-scrollbar-track{background:transparent}
.sidebar .brand{padding:0 24px 20px; border-bottom:1px solid #334155; margin-bottom:16px}
.sidebar .brand h1{font-size:16px; margin:0 0 4px; color:#fff; font-weight:700; letter-spacing:.5px}
.sidebar .brand .sub{font-size:11px; color:#94a3b8}
.sidebar .brand .badge{
  display:inline-block; margin-top:10px; padding:3px 10px; font-size:11px;
  background:rgba(59,130,246,.2); color:#93c5fd; border-radius:4px; border:1px solid rgba(59,130,246,.3);
}
.toc{padding:0 12px}
.toc ul{list-style:none; padding-left:12px; margin:4px 0}
.toc > ul{padding-left:0}
.toc li{margin:2px 0}
.toc a{
  display:block; padding:5px 10px; font-size:13px; color:#cbd5e1;
  text-decoration:none; border-radius:4px; border-left:2px solid transparent;
  transition:all .15s;
}
.toc a:hover{background:rgba(59,130,246,.15); color:#fff; border-left-color:#3b82f6}
.toc > ul > li > a{font-weight:600; color:#e2e8f0; padding-left:10px}
.toc ul ul ul a{font-size:12px; padding-left:22px; color:#94a3b8}

/* 主内容 */
.content{max-width:960px; margin:0 auto; padding:40px 48px 120px}

/* 标题 */
.content h1{
  font-size:28px; margin:0 0 12px; color:#0f172a;
  padding-bottom:14px; border-bottom:3px solid var(--primary);
}
.content h2{
  font-size:20px; margin:40px 0 18px; color:#0f172a;
  padding:10px 16px; background:linear-gradient(90deg,#eff6ff 0%,transparent 100%);
  border-left:4px solid var(--primary); border-radius:0 6px 6px 0;
}
.content h3{
  font-size:16px; margin:28px 0 12px; color:#1e40af;
  padding-bottom:6px; border-bottom:1px dashed var(--border-2);
}
.content h4{font-size:14px; margin:20px 0 8px; color:#334155}

/* 引用块 */
.content blockquote{
  margin:16px 0; padding:12px 18px; border-left:4px solid var(--accent);
  background:#ecfeff; border-radius:0 6px 6px 0; color:#0c4a6e; font-size:13.5px;
}
.content blockquote strong{color:#075985}

/* 段落 */
.content p{margin:10px 0}

/* 公式 */
.content code{
  font-family:'JetBrains Mono','Fira Code','Consolas',monospace;
  background:#f1f5f9; color:#db2777; padding:2px 6px; border-radius:3px;
  font-size:13px; border:1px solid #e2e8f0;
}
.content pre{
  background:var(--code-bg); color:var(--code-text); padding:16px 20px;
  border-radius:8px; overflow-x:auto; font-size:13px; line-height:1.6;
  margin:14px 0; box-shadow:var(--shadow); border:1px solid #1e293b;
}
.content pre code{background:transparent; border:none; color:inherit; padding:0; font-size:inherit}

/* 表格 */
.content table{
  border-collapse:collapse; width:100%; margin:14px 0;
  font-size:13px; box-shadow:var(--shadow); border-radius:6px; overflow:hidden;
}
.content thead tr{background:linear-gradient(180deg,#f1f5f9 0%,#e2e8f0 100%)}
.content th{padding:10px 14px; text-align:left; font-weight:600; color:#334155; border:1px solid var(--border)}
.content td{padding:9px 14px; border:1px solid var(--border); color:var(--text-2)}
.content tbody tr:nth-child(even){background:#fafbfc}
.content tbody tr:hover{background:#eff6ff}
.content td:first-child{font-weight:500; color:#1e293b; white-space:nowrap}

/* 分隔线 */
.content hr{
  border:none; height:1px; background:linear-gradient(90deg,transparent,var(--border-2),transparent);
  margin:40px 0;
}

/* 列表 */
.content ul, .content ol{margin:8px 0; padding-left:24px}
.content li{margin:4px 0}

/* 链接 */
.content a{color:var(--primary); text-decoration:none; border-bottom:1px dashed var(--primary)}
.content a:hover{color:var(--primary-dark); border-bottom-style:solid}

/* 打印 */
@media print{
  .layout{display:block}
  .sidebar{display:none}
  .content{max-width:100%; padding:0}
  body{background:#fff}
}

/* 响应式 */
@media(max-width:900px){
  .layout{grid-template-columns:1fr}
  .sidebar{position:relative; height:auto}
}

/* 修订标记 */
.revision-hint{
  display:inline-block; margin-top:6px; padding:4px 10px; font-size:12px;
  background:#fef3c7; color:#92400e; border-radius:4px; border:1px solid #fde68a;
}
</style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="brand">
    <h1>KELKCalCv</h1>
    <div class="sub">调节阀 Cv 计算 &amp; 噪音预测</div>
    <span class="badge">计算过程文档 v1.0</span>
  </div>
  <nav class="toc">__TOC__</nav>
</aside>
<main class="content">__BODY__</main>
</div>
</body>
</html>
'''

html = HTML_TEMPLATE.replace('__TOC__', toc_html).replace('__BODY__', body_main)

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'生成成功! 大小 = {len(html):,} bytes')
print(f'输出路径: {HTML_PATH}')
