/* رندر Markdown — سبک، بدون وابستگی، برای پاسخ دستیار و متن پروفایل.
   پشتیبانی: تیتر، تأکید، فهرست تودرتو، جدول، کد، نقل‌قول، خط افقی، لینک. */
'use strict';

const MD = (() => {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function inline(s) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>');
    s = s.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s;
  }

  function render(src) {
    const lines = String(src ?? '').replace(/\r/g, '').split('\n');
    const out = [];
    let i = 0;

    const listStack = [];   // {tag, indent}
    const closeLists = (toIndent = -1) => {
      while (listStack.length && listStack[listStack.length - 1].indent > toIndent) {
        out.push(`</${listStack.pop().tag}>`);
      }
    };

    while (i < lines.length) {
      const raw = lines[i];
      const line = raw.trimEnd();

      // بلوک کد
      if (/^\s*```/.test(line)) {
        closeLists();
        const buf = [];
        i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) buf.push(lines[i++]);
        i++;
        out.push(`<pre class="mdcode"><code>${esc(buf.join('\n'))}</code></pre>`);
        continue;
      }

      // جدول
      if (line.includes('|') && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1])) {
        closeLists();
        const cells = r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
        const head = cells(line);
        i += 2;
        const body = [];
        while (i < lines.length && lines[i].includes('|') && lines[i].trim()) body.push(cells(lines[i++]));
        out.push('<div class="mdtablewrap"><table class="mdtable"><thead><tr>' +
          head.map(h => `<th>${inline(h)}</th>`).join('') + '</tr></thead><tbody>' +
          body.map(r => '<tr>' + r.map(c => {
            const num = /^[-+]?[\d,.\s٪%]+$/.test(c.replace(/[*_]/g, ''));
            return `<td class="${num ? 'num' : ''}">${inline(c)}</td>`;
          }).join('') + '</tr>').join('') + '</tbody></table></div>');
        continue;
      }

      // تیتر
      let m = line.match(/^(#{1,6})\s+(.*)$/);
      if (m) {
        closeLists();
        const lv = Math.min(6, m[1].length + 2);
        out.push(`<h${lv} class="mdh">${inline(m[2])}</h${lv}>`);
        i++;
        continue;
      }

      // خط افقی
      if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
        closeLists();
        out.push('<hr class="mdhr">');
        i++;
        continue;
      }

      // نقل‌قول
      if (/^\s*>\s?/.test(line)) {
        closeLists();
        const buf = [];
        while (i < lines.length && /^\s*>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ''));
        out.push(`<blockquote class="mdquote">${inline(buf.join(' '))}</blockquote>`);
        continue;
      }

      // فهرست
      m = line.match(/^(\s*)([-*•]|\d+[.)])\s+(.*)$/);
      if (m) {
        const indent = m[1].replace(/\t/g, '    ').length;
        const ordered = /\d/.test(m[2]);
        const tag = ordered ? 'ol' : 'ul';
        if (!listStack.length || indent > listStack[listStack.length - 1].indent) {
          out.push(`<${tag} class="mdlist">`);
          listStack.push({ tag, indent });
        } else {
          closeLists(indent);
          if (!listStack.length) { out.push(`<${tag} class="mdlist">`); listStack.push({ tag, indent }); }
        }
        out.push(`<li>${inline(m[3])}</li>`);
        i++;
        continue;
      }

      // خط خالی
      if (!line.trim()) { closeLists(); i++; continue; }

      // پاراگراف
      closeLists();
      const buf = [line];
      i++;
      while (i < lines.length && lines[i].trim() && !/^(\s*)([-*•]|\d+[.)])\s+/.test(lines[i]) &&
        !/^#{1,6}\s/.test(lines[i]) && !lines[i].includes('|') && !/^\s*>/.test(lines[i])) {
        buf.push(lines[i++]);
      }
      out.push(`<p class="mdp">${inline(buf.join(' '))}</p>`);
    }
    closeLists();
    return out.join('\n');
  }

  return { render, inline, esc };
})();
