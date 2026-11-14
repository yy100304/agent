/**
 * 轻量 Markdown 渲染（演示用，覆盖 Agent 输出模板的语法子集）：
 * 标题 / 引用 / 加粗 / 行内代码 / 无序与有序列表 / 分隔线 / 换行
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

export function renderMarkdown(md: string): string {
  const lines = escapeHtml(md).split('\n')
  const out: string[] = []
  let inList = false

  const closeList = () => {
    if (inList) {
      out.push('</ul>')
      inList = false
    }
  }

  const inline = (s: string): string =>
    s
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')

  for (const raw of lines) {
    const line = raw.trimEnd()

    if (/^###\s+/.test(line)) {
      closeList()
      out.push(`<h4>${inline(line.replace(/^###\s+/, ''))}</h4>`)
    } else if (/^##\s+/.test(line)) {
      closeList()
      out.push(`<h3>${inline(line.replace(/^##\s+/, ''))}</h3>`)
    } else if (/^#\s+/.test(line)) {
      closeList()
      out.push(`<h2>${inline(line.replace(/^#\s+/, ''))}</h2>`)
    } else if (/^>\s?/.test(line)) {
      closeList()
      out.push(`<blockquote>${inline(line.replace(/^>\s?/, ''))}</blockquote>`)
    } else if (/^(-{3,}|---+)\s*$/.test(line)) {
      closeList()
      out.push('<hr />')
    } else if (/^[---]\s+/.test(line) || /^-\s+/.test(line)) {
      if (!inList) {
        out.push('<ul>')
        inList = true
      }
      out.push(`<li>${inline(line.replace(/^[-]+\s+/, ''))}</li>`)
    } else if (/^\d+\.\s+/.test(line)) {
      if (!inList) {
        out.push('<ul class="md-ol">')
        inList = true
      }
      out.push(
        `<li><span class="md-num">${line.match(/^\d+/)?.[0]}.</span> ${inline(
          line.replace(/^\d+\.\s+/, '')
        )}</li>`
      )
    } else if (line === '') {
      closeList()
    } else {
      closeList()
      out.push(`<p>${inline(line)}</p>`)
    }
  }
  closeList()
  return out.join('\n')
}
