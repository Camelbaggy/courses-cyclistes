#!/usr/bin/env python3
"""Captures d'écran de index.html (390x844) sur le jeu de données fictif tools/fixtures/data.

Sert le dépôt en local (http.server, port libre, dans un thread) puis pilote Chromium avec Playwright
(paquet Python s'il existe, sinon Node via NODE_PATH). Journalise les erreurs console et détecte tout
débordement horizontal.

    python tools/apercu.py <dossier_de_sortie> [--data tools/fixtures/data] [--sombre] [--nav]

Le dossier de sortie est obligatoire (créé s'il n'existe pas) : aucun chemin par défaut.
"""
import argparse
import functools
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
NODE_PATH = "/opt/node-tools/node_modules"

# Script Node (Playwright). Reçoit sa configuration en JSON dans APERCU_CONF.
SCRIPT_NODE = r"""
const { chromium } = require('playwright');
const conf = JSON.parse(process.env.APERCU_CONF);
const FLAG_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="28"><rect width="40" height="28" fill="#94a3b8"/><rect y="9" width="40" height="10" fill="#e2e8f0"/></svg>';
(async () => {
  const opts = { headless: true };
  if (conf.chromium) opts.executablePath = conf.chromium;
  const browser = await chromium.launch(opts);
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1,
                                          colorScheme: conf.scheme });
  await ctx.route('https://flagcdn.com/**', r => r.fulfill({ status: 200, contentType: 'image/svg+xml', body: FLAG_SVG }));
  const page = await ctx.newPage();
  const erreurs = [];
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) erreurs.push(`[console.${m.type()}] ${m.text()}`); });
  page.on('pageerror', e => erreurs.push(`[pageerror] ${e.message}`));
  page.on('requestfailed', r => { if (!r.url().includes('flagcdn')) erreurs.push(`[requestfailed] ${r.url()}`); });
  const base = `http://127.0.0.1:${conf.port}/index.html?data=${conf.data}`;
  const sortie = conf.sortie, suf = conf.suffixe;
  const debord = [];
  async function verifie(nom) {
    const r = await page.evaluate(() => {
      const rs = document.getElementById('rsheet');
      const sheet = rs.classList.contains('open') ? rs : document.getElementById('sheet');
      const ouvert = sheet.classList.contains('open');
      const el = ouvert ? sheet : document.documentElement;
      const pires = [];
      document.querySelectorAll(ouvert ? `#${sheet.id} *` : 'header.top *, main *').forEach(n => {
        const b = n.getBoundingClientRect();
        if (b.width > 0 && b.right > 391 && getComputedStyle(n).position !== 'fixed' && !n.closest('.chips,.subtabs')) pires.push(n.className || n.tagName);
      });
      return { sw: el.scrollWidth, cw: el.clientWidth, pires: pires.slice(0, 5) };
    });
    if (r.sw > r.cw + 1 || r.pires.length) debord.push(`${nom}: scrollWidth=${r.sw} clientWidth=${r.cw} ${r.pires.join(',')}`);
  }
  async function cap(nom, full) {
    await page.waitForTimeout(250);
    await verifie(nom);
    await page.screenshot({ path: `${sortie}/${nom}${suf}.png`, fullPage: !!full });
    console.log('capture', `${nom}${suf}.png`);
  }
  async function hauteurFiche(nom) {
    // la fiche défile dans #sheet : on agrandit temporairement la fenêtre pour une capture complète
    const h = await page.evaluate(() => document.getElementById('sheet-body').scrollHeight + 60);
    await page.setViewportSize({ width: 390, height: Math.min(h, 4000) });
    await cap(nom);
    await page.setViewportSize({ width: 390, height: 844 });
  }

  await page.goto(base); await page.waitForSelector('.card');
  await cap('01-recents', true);
  // Calendrier : saison en cours, puis autre saison ; Résultats / À venir ; filtre WT
  await page.click('.tab[data-tab="calendrier"]'); await page.waitForSelector('#cal-saisons'); await page.waitForSelector('.cal-item');
  await cap('02a-calendrier-resultats', true);
  await page.click('[data-calvue="avenir"]'); await cap('02b-calendrier-avenir-vide', false);
  const saisons = await page.$$eval('[data-calsaison]', b => b.map(x => x.dataset.calsaison));
  for (const y of saisons.slice(0, 2)) {
    await page.click(`[data-calsaison="${y}"]`); await page.waitForTimeout(400);
    await page.click('[data-calvue="resultats"]'); await cap(`02c-calendrier-${y}-resultats`, false);
    await page.click('[data-calvue="avenir"]'); await cap(`02d-calendrier-${y}-avenir`, false);
  }
  await page.click('.chip[data-cat="WT"]'); await cap('02e-calendrier-avenir-wt', false);
  await page.click('.chip[data-cat="all"]');
  // Classements : UCI (recherche, Français, plus), FDJ Series
  await page.click('.tab[data-tab="classements"]'); await page.waitForSelector('.row.uc, .empty');
  await cap('03a-classement-uci', false);
  if (await page.$('#uc-q')) {
    await page.click('[data-action="uc-more"]').catch(() => {}); await cap('03b-uci-plus', false);
    await page.click('[data-action="uc-fr"]'); await cap('03c-uci-francais', false);
    await page.click('[data-action="uc-fr"]'); await page.fill('#uc-q', 'ebauche'); await cap('03d-uci-recherche', false);
    await page.fill('#uc-q', '');
    const lien = await page.$('#uc-list .rlink');
    if (lien) { await lien.click(); await page.waitForSelector('#rsheet.open .tile'); await cap('03e-uci-fiche-coureur', false); await page.click('#rsheet [data-action="back"]'); await page.waitForTimeout(300); }
  }
  await page.click('[data-clsub="fdj"]'); await cap('03f-classement-fdj', true);
  await page.click('.tab[data-tab="francais"]'); await page.waitForSelector('.fr-card'); await cap('04a-francais', false);
  await page.evaluate(() => document.querySelector('details.nc') && (document.querySelector('details.nc').open = true));
  await cap('04b-francais-complet', true);
  await page.click('.fr-card'); await page.waitForSelector('#rsheet.open .tile'); await cap('04c-francais-fiche', false);
  await page.click('#rsheet [data-action="back"]'); await page.waitForTimeout(300);
  // fiche coureur ouverte depuis le calendrier d'une autre saison (riders-<saison>)
  await page.goto(base + '&saison=' + saisons[0]); await page.waitForSelector('.card');
  await page.click('.tab[data-tab="calendrier"]'); await page.click(`[data-calsaison="${saisons[0]}"]`); await page.waitForSelector('.cal-item');
  await page.click('.cal-item.click, button.cal-item'); await page.waitForSelector('#sheet.open .card');
  const rl = await page.$('#sheet .rlink'); if (rl) { await rl.click(); await page.waitForSelector('#rsheet.open .tile'); await cap('05-fiche-coureur-saison', false); }
  await page.goto(base); await page.waitForSelector('.card');
  await cap('01-recents', true);
  // Archives : onglet par défaut (saison la plus récente), liste vide si aucune archive
  await page.goto(base); await page.waitForSelector('.card');
  await page.click('.tab[data-tab="archives"]'); await page.waitForSelector('#arch-sel, .empty');
  await page.waitForSelector('.cal-item, .empty, .errbox'); await cap('06a-archives', true);
  if (conf.navonly) { await browser.close(); console.log('ERREURS_CONSOLE', JSON.stringify(erreurs)); console.log('DEBORDEMENTS', JSON.stringify(debord)); return; }

  // Archives (jeu fictif) : autre saison via le select, filtre, fiches course et coureur d'archive
  await page.selectOption('#arch-sel', '2023'); await page.waitForSelector('.arch-note'); await cap('06b-archives-2023-en-cours', true);
  await page.selectOption('#arch-sel', '2024'); await page.waitForSelector('.cal-item');
  await page.click('[data-acat="Pro"]'); await cap('06c-archives-filtre-pro', false);
  await page.click('[data-acat="all"]');
  console.log('url archives :', await page.evaluate(() => location.search));
  await page.click('[data-open="fx-a24-tour-hc"].cal-item'); await page.waitForSelector('#sheet.open .card');
  await cap('07a-archive-fiche-etapes', false);
  await hauteurFiche('07b-archive-fiche-complete');
  const rlA = await page.$('#sheet .rlink'); await rlA.click(); await page.waitForSelector('#rsheet.open .tile');
  await cap('07c-archive-fiche-coureur', false);
  await page.click('#rsheet [data-action="back"]'); await page.click('#sheet [data-action="back"]'); await page.waitForTimeout(300);
  await page.goto(base + '&archive=2023'); await page.waitForSelector('.cal-item');
  await page.click('.cal-item.click, button.cal-item'); await page.waitForSelector('#sheet.open .card');
  const rlB = await page.$('#sheet .rlink'); await rlB.click(); await page.waitForSelector('#rsheet.open .empty');
  await cap('07d-archive-coureur-sans-riders', false);
  // lien direct vers une course d'archive (404 volontaire sur races/, puis recherche dans les archives)
  const avantA = erreurs.length;
  await page.goto(base + '#course/fx-a24-classique-hc'); await page.waitForSelector('#sheet.open .card');
  await cap('07e-archive-lien-direct', false);
  const rlC = await page.$('#sheet .rlink'); await rlC.click(); await page.waitForSelector('#rsheet.open .tile');
  const saison = await page.evaluate(() => document.getElementById('rsheet-body').textContent.includes('Palmarès de la saison 2024'));
  console.log('lien direct archive : fiche coureur de la saison 2024 :', saison);
  console.log('ERREURS_ATTENDUES (404 lien direct)', JSON.stringify(erreurs.splice(avantA)));
  await page.goto(base);

  // fiche course par étapes (étape la plus récente)
  await page.goto(base + '#course/fx-tour-test'); await page.waitForSelector('#sheet.open .card');
  await cap('10-fiche-etape', false);
  await hauteurFiche('11-fiche-etape-complete');
  await page.click('[data-sub="gc"]'); await page.evaluate(() => document.getElementById('sheet').scrollTo(0, document.getElementById('table').offsetTop - 60));
  await cap('12-fiche-general', false);
  await page.click('[data-action="fronly"]'); await cap('13-general-francais', false);
  await page.click('[data-action="fronly"]');
  await page.click('[data-sub="abandons"]'); await page.evaluate(() => document.getElementById('sheet').scrollTo(0, document.getElementById('table').offsetTop - 60));
  await cap('14-fiche-abandons', false);
  // contre-la-montre, montagne sans résumé, prologue
  await page.click('[data-stage-sel="5"]'); await page.evaluate(() => document.getElementById('sheet').scrollTo(0, 0)); await cap('15-clm', false);
  await page.click('[data-stage-sel="3"]'); await page.evaluate(() => document.getElementById('sheet').scrollTo(0, 0)); await cap('16-montagne-sans-resume', false);
  await page.click('[data-stage-sel="0"]'); await page.evaluate(() => document.getElementById('sheet').scrollTo(0, 0)); await cap('17-prologue', false);
  // classique pavés et course .1 française
  await page.goto(base + '#course/fx-classique-paves'); await page.waitForSelector('#sheet.open .card');
  await hauteurFiche('20-classique-paves');
  await page.goto(base + '#course/fx-gp-test-sur-mer'); await page.waitForSelector('#sheet.open .card');
  await cap('21-course-1-fr', false);
  // erreur de chargement
  const avant = erreurs.length;
  await page.goto(base + '#course/inexistante'); await page.waitForSelector('.errbox');
  await cap('22-erreur', false);
  console.log('ERREURS_ATTENDUES (404 volontaire)', JSON.stringify(erreurs.splice(avant)));
  // retour par bouton
  await page.goto(base); await page.waitForSelector('.card');
  await page.click('[data-open]'); await page.waitForSelector('#sheet.open'); await page.click('[data-action="back"]');
  await page.waitForTimeout(300);
  const ferme = await page.evaluate(() => !document.getElementById('sheet').classList.contains('open') && location.hash === '');
  console.log('retour bouton ferme la fiche et vide le hash :', ferme);

  await browser.close();
  console.log('ERREURS_CONSOLE', JSON.stringify(erreurs));
  console.log('DEBORDEMENTS', JSON.stringify(debord));
})().catch(e => { console.error('ECHEC', e); process.exit(1); });
"""


def serveur(racine):
    class Silencieux(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    gestionnaire = functools.partial(Silencieux, directory=str(racine))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), gestionnaire)   # port 0 = port libre
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sortie", help="dossier de sortie des captures (obligatoire)")
    ap.add_argument("--data", default="tools/fixtures/data", help="dossier de données relatif à la racine du dépôt")
    ap.add_argument("--nav", action="store_true", help="seulement les onglets (données réelles : sans les fiches fictives)")
    ap.add_argument("--sombre", action="store_true", help="thème sombre (suffixe -sombre sur les fichiers)")
    args = ap.parse_args()
    sortie = Path(args.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    srv = serveur(RACINE)
    port = srv.server_address[1]
    print(f"[INFO] serveur local sur 127.0.0.1:{port}, captures dans {sortie}")
    chromium = None
    for p in sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")):
        chromium = str(p)
    conf = {"port": port, "data": args.data, "sortie": str(sortie), "chromium": chromium,
            "scheme": "dark" if args.sombre else "light", "suffixe": "-sombre" if args.sombre else "", "navonly": args.nav}
    env = dict(os.environ, NODE_PATH=NODE_PATH, APERCU_CONF=json.dumps(conf))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(SCRIPT_NODE)
        script = f.name
    try:
        r = subprocess.run(["node", script], env=env, capture_output=True, text=True, timeout=300)
    finally:
        os.unlink(script)
    print(r.stdout)
    if r.returncode:
        print(r.stderr, file=sys.stderr)
    srv.shutdown()
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
