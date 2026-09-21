(function (root) {
  'use strict';
  function mentionAt(value, caret) {
    const before = value.slice(0, caret);
    const match = /(^|\s)@([^@"\n]*)$/.exec(before);
    return match ? {start: match.index + match[1].length, end: caret, prefix: match[2]} : null;
  }
  function splitQuery(value, selected) {
    const people = [];
    const query = value.replace(/@"(?:\\.|[^"\\])*"/g, token => {
      const person = selected.get(token);
      if (!person) return token;
      if (!people.includes(person.id)) people.push(person.id);
      return ' ';
    }).replace(/\s+/g, ' ').trim();
    return {query, people};
  }
  function create({inputs, onDraft, onSubmit, texts}) {
    const selected = new Map();
    const menu = document.createElement('div');
    menu.className = 'person-search-menu';
    menu.id = 'person-search-suggestions';
    menu.setAttribute('role', 'listbox');
    menu.setAttribute('aria-label', texts().people);
    menu.hidden = true;
    document.body.append(menu);
    let input = null, mention = null, items = [], active = 0, timer, request, generation = 0;
    function close() {
      generation++;
      clearTimeout(timer);
      if (request) request.abort();
      menu.hidden = true;
      for (const field of inputs) {
        field.setAttribute('aria-expanded', 'false');
        field.removeAttribute('aria-activedescendant');
      }
    }
    function position() {
      if (!input || menu.hidden) return;
      const box = input.getBoundingClientRect();
      const width = Math.min(Math.max(box.width, 260), innerWidth - 16);
      menu.style.width = width + 'px';
      menu.style.left = Math.max(8, Math.min(box.left, innerWidth - width - 8)) + 'px';
      menu.style.top = Math.min(box.bottom + 6, innerHeight - 80) + 'px';
      menu.style.maxHeight = Math.max(64, Math.min(300, innerHeight - box.bottom - 18)) + 'px';
    }
    function render(message, more = false) {
      menu.replaceChildren();
      items.forEach((person, index) => {
        const button = document.createElement('div');
        button.className = 'person-search-option';
        button.id = 'person-search-option-' + index;
        button.setAttribute('role', 'option');
        button.setAttribute('aria-selected', String(index === active));
        button.textContent = person.name;
        button.addEventListener('pointerdown', event => {
          event.preventDefault(); event.stopPropagation(); choose(index);
        });
        menu.append(button);
      });
      if (message || more) {
        const note = document.createElement('div');
        note.className = 'person-search-note';
        note.setAttribute('role', 'status');
        note.textContent = message || texts().more;
        menu.append(note);
      }
      menu.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      if (items.length) input.setAttribute('aria-activedescendant', 'person-search-option-' + active);
      else input.removeAttribute('aria-activedescendant');
      position();
    }
    function choose(index) {
      const person = items[index];
      if (!person || !mention) return;
      let label = person.name, token = '@' + JSON.stringify(label), suffix = 2;
      while (selected.has(token) && selected.get(token).id !== person.id) {
        token = '@' + JSON.stringify(label + ' (' + suffix++ + ')');
      }
      selected.set(token, person);
      const value = input.value.slice(0, mention.start) + token + ' ' + input.value.slice(mention.end).replace(/^\s+/, '');
      const caret = mention.start + token.length + 1;
      input.value = value;
      onDraft(value);
      close();
      input.focus(); input.setSelectionRange(caret, caret);
    }
    function update(field) {
      close(); input = field;
      mention = mentionAt(field.value, field.selectionStart ?? field.value.length);
      if (!mention) return;
      items = []; active = 0;
      render(texts().loading);
      const version = generation, prefix = mention.prefix;
      timer = setTimeout(async () => {
        const controller = new AbortController(); request = controller;
        const timeout = setTimeout(() => controller.abort(), 8000);
        try {
          const response = await fetch('/api/people/suggest?q=' + encodeURIComponent(prefix), {signal: controller.signal});
          if (!response.ok) throw new Error('suggestions');
          const data = await response.json();
          if (generation !== version) return;
          items = Array.isArray(data.items) ? data.items : [];
          render(items.length ? '' : texts().empty, data.has_more);
        } catch (_) {
          if (generation === version) render(texts().error);
        } finally { clearTimeout(timeout); }
      }, 120);
    }
    for (const field of inputs) {
      field.setAttribute('role', 'combobox');
      field.setAttribute('aria-autocomplete', 'list');
      field.setAttribute('aria-controls', menu.id);
      field.setAttribute('aria-expanded', 'false');
      field.setAttribute('autocomplete', 'off');
      field.addEventListener('input', () => { onDraft(field.value); update(field); });
      field.addEventListener('click', () => update(field));
      field.addEventListener('focus', () => update(field));
      field.addEventListener('keydown', event => {
        if (event.isComposing) return;
        if (event.key === 'Escape' && !menu.hidden) {
          event.preventDefault(); event.stopImmediatePropagation(); close(); return;
        }
        if (!menu.hidden && items.length && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
          event.preventDefault(); event.stopImmediatePropagation();
          active = (active + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
          render(''); menu.children[active].scrollIntoView({block: 'nearest'}); return;
        }
        if (event.key === 'Enter') {
          event.preventDefault(); event.stopImmediatePropagation();
          if (!menu.hidden && items.length) choose(active);
          else { close(); onSubmit(field.value); }
        }
        if (event.key === 'Tab') close();
      }, true);
    }
    document.addEventListener('pointerdown', event => {
      if (!inputs.includes(event.target) && !menu.contains(event.target)) close();
    });
    window.addEventListener('resize', position);
    window.addEventListener('scroll', position, {passive: true, capture: true});
    return {parse: value => splitQuery(value, selected), close};
  }
  root.PersonSearch = {mentionAt, splitQuery, create};
  if (typeof module !== 'undefined') module.exports = root.PersonSearch;
})(typeof window !== 'undefined' ? window : globalThis);
