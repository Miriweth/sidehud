const STRINGS = {
  en: {
    date: '{wd}, {day} {season}, Year {year}', money: 'Money', energy: 'Energy', health: 'Health', luck: 'Luck',
    birthday: 'Birthday', festival: 'Festival',
    season: { spring: 'Spring', summer: 'Summer', fall: 'Fall', winter: 'Winter' },
    weekday: { Mon: 'Mon', Tue: 'Tue', Wed: 'Wed', Thu: 'Thu', Fri: 'Fri', Sat: 'Sat', Sun: 'Sun' },
    weather: { sunny: 'sunny', rain: 'rain', storm: 'storm', snow: 'snow', wind: 'windy', greenrain: 'green rain' },
    luckWords: ['very bad', 'bad', 'neutral', 'good', 'very good'],
    skill: { farming: 'Farming', mining: 'Mining', foraging: 'Foraging', fishing: 'Fishing', combat: 'Combat' },
  },
  de: {
    date: '{wd}, {day}. {season}, Jahr {year}', money: 'Geld', energy: 'Energie', health: 'Gesundheit', luck: 'Glück',
    birthday: 'Geburtstag', festival: 'Fest',
    season: { spring: 'Frühling', summer: 'Sommer', fall: 'Herbst', winter: 'Winter' },
    weekday: { Mon: 'Mo', Tue: 'Di', Wed: 'Mi', Thu: 'Do', Fri: 'Fr', Sat: 'Sa', Sun: 'So' },
    weather: { sunny: 'sonnig', rain: 'Regen', storm: 'Gewitter', snow: 'Schnee', wind: 'windig', greenrain: 'grüner Regen' },
    luckWords: ['sehr schlecht', 'schlecht', 'neutral', 'gut', 'sehr gut'],
    skill: { farming: 'Landwirtschaft', mining: 'Bergbau', foraging: 'Sammeln', fishing: 'Angeln', combat: 'Kampf' },
  },
};
const SKILLS = ['farming', 'mining', 'foraging', 'fishing', 'combat'];

let ui = null;

function build(root, s) {
  root.innerHTML = `
    <div class="value"><span class="time">–</span></div>
    <div class="caption"><span class="date"></span> · <span class="weather"></span></div>
    <div class="kv"><span class="k">${s.money}</span><span class="v money">–</span></div>
    <div class="kv"><span class="k">${s.energy}</span><span class="v energy">–</span></div>
    <div class="meter" style="--c:var(--mem)"><div class="fill energy-fill"></div></div>
    <div class="kv"><span class="k">${s.health}</span><span class="v health">–</span></div>
    <div class="meter health-meter" style="--c:var(--cpu)"><div class="fill health-fill"></div></div>
    <div class="kv"><span class="k">${s.luck}</span><span class="v luck">–</span></div>
    <div class="caption skills"></div>
    <div class="caption event hidden"></div>`;
  const q = c => root.querySelector('.' + c);
  return {
    root, time: q('time'), date: q('date'), weather: q('weather'), money: q('money'),
    energy: q('energy'), energyFill: q('energy-fill'), health: q('health'), healthMeter: q('health-meter'),
    healthFill: q('health-fill'), luck: q('luck'), skills: q('skills'), event: q('event'),
  };
}

const set = (el, text) => { if (el.textContent !== text) el.textContent = text; };
const pct = (v, max) => max ? Math.max(0, Math.min(100, v / max * 100)) : 0;
const luckIndex = v => v < -0.07 ? 0 : v < -0.02 ? 1 : v <= 0.02 ? 2 : v <= 0.07 ? 3 : 4;
const clock = (t, lang) => {
  if (t == null) return null;
  const h = Math.floor(t / 100) % 24, m = String(t % 100).padStart(2, '0');
  return lang === 'de' ? `${h}:${m}` : `${h % 12 || 12}:${m} ${h < 12 ? 'am' : 'pm'}`;
};

function render(stats, root, ctx) {
  const s = STRINGS[ctx.lang] || STRINGS.en;
  if (!ui || !ui.time.isConnected) ui = build(root, s);
  const date = stats.day == null ? '' : s.date.replace('{wd}', s.weekday[stats.weekday] || stats.weekday || '')
    .replace('{day}', stats.day)
    .replace('{season}', s.season[stats.season] || stats.season || '')
    .replace('{year}', stats.year ?? '');
  set(ui.time, clock(stats.time, ctx.lang) || stats.timeText || '–');
  set(ui.date, date);
  set(ui.weather, s.weather[stats.weather] || stats.weather || '');
  set(ui.money, stats.money != null ? ctx.f0(stats.money) + ' g' : '–');
  set(ui.energy, `${ctx.f0(stats.energy)} / ${ctx.f0(stats.maxEnergy)}`);
  ui.energyFill.style.width = pct(stats.energy, stats.maxEnergy) + '%';
  const hp = pct(stats.health, stats.maxHealth);
  set(ui.health, `${ctx.f0(stats.health)} / ${ctx.f0(stats.maxHealth)}`);
  ui.healthFill.style.width = hp + '%';
  ui.healthMeter.classList.toggle('crit', stats.health != null && hp < 30);
  set(ui.luck, stats.luck != null ? s.luckWords[luckIndex(stats.luck)] : '–');
  const sk = stats.skills || {};
  set(ui.skills, SKILLS.map(k => `${s.skill[k]} ${sk[k] ?? '–'}`).join(' · '));
  const events = [];
  if (stats.birthday) events.push(`${s.birthday}: ${stats.birthday}`);
  if (stats.festival) events.push(`${s.festival}: ${stats.festival}`);
  set(ui.event, events.join(' · '));
  ui.event.classList.toggle('hidden', !events.length);
  return { sub: stats.location || '' };
}

export default { title: 'Stardew Valley', render };
