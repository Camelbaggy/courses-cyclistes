#!/usr/bin/env python3
"""Captures d'écran de index.html (encyclopédie : accueil, courses, épreuves, éditions, équipes, coureurs, classements, recherche).

Sert un dossier en local (http.server, port libre, dans un thread) puis pilote Chromium avec Playwright (Node via NODE_PATH).
Chaque page est capturée à 390 px (mobile, suffixe -m) et 1024 px (suffixe -d) ; le script journalise les erreurs console,
détecte tout débordement horizontal, vérifie la navigation arrière, l'ancienne URL ?archive= et les zones tactiles de la barre du bas.

    python tools/apercu.py <dossier_de_sortie> [--data tools/fixtures/data]            # jeu fictif (par défaut)
    python tools/apercu.py <dossier_de_sortie> --reel <dossier_servi> [--archives archives]   # données réelles (captures vrai-*)

`--reel` : le dossier servi contient index.html, `data` et `archives` (liens vers les vraies données, lecture seule) ;
le paramètre ?archives= est transmis à la page. Le dossier de sortie est obligatoire (créé s'il n'existe pas).
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
  const sortie = conf.sortie;
  const erreurs = [], debord = [], echecs = [];
  const nouveauContexte = async (w, h) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, colorScheme: 'dark' });
    await ctx.route('https://flagcdn.com/**', r => r.fulfill({ status: 200, contentType: 'image/svg+xml', body: FLAG_SVG }));
    const page = await ctx.newPage();
    page.on('console', m => { if (['error', 'warning'].includes(m.type())) erreurs.push(`[console.${m.type()}] ${m.text()} ${m.location().url || ''}`); });
    page.on('pageerror', e => erreurs.push(`[pageerror] ${e.message}`));
    page.on('requestfailed', r => { if (!r.url().includes('flagcdn')) erreurs.push(`[requestfailed] ${r.url()}`); });
    return { ctx, page };
  };
  const archives = conf.archives ? `&archives=${conf.archives}` : '';
  const url = (hash) => conf.reel ? `http://127.0.0.1:${conf.port}/index.html?x=1${archives}${hash || ''}`
                                  : `http://127.0.0.1:${conf.port}/index.html?data=${conf.data}${hash || ''}`;
  const ok = (nom, cond, detail) => { console.log(cond ? 'OK   ' : 'ECHEC', nom, detail === undefined ? '' : JSON.stringify(detail)); if (!cond) echecs.push(nom); };

  async function pret(page, sel) {
    await page.waitForSelector(sel || '#main .pg, #main .art, #main .home, #main .errbox', { timeout: 20000 });
    await page.waitForFunction(() => !document.querySelector('#main .loading, #main [aria-busy="true"]'), null, { timeout: 20000 });
    await page.waitForTimeout(200);
  }
  async function verifie(page, nom) {
    const r = await page.evaluate(() => {
      const pires = [];
      document.querySelectorAll('header.top *, main *, .bnav *').forEach(n => {
        const b = n.getBoundingClientRect();
        if (b.width > 0 && b.right > window.innerWidth + 1 && getComputedStyle(n).position !== 'fixed' && !n.closest('.chips,.subtabs,.tbl-wrap,.sr-only,.sr')) pires.push(n.className || n.tagName);
      });
      const d = document.documentElement;
      return { sw: d.scrollWidth, cw: d.clientWidth, pires: pires.slice(0, 5) };
    });
    if (r.sw > r.cw + 1 || r.pires.length) debord.push(`${nom}: scrollWidth=${r.sw} clientWidth=${r.cw} ${r.pires.join(',')}`);
  }
  async function cap(page, nom, suf, opt) {
    opt = opt || {};
    await page.waitForTimeout(250);
    if (opt.defile) { await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight)); await page.waitForTimeout(600); await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(250); }
    await verifie(page, nom + suf);
    await page.screenshot({ path: `${sortie}/${conf.prefixe}${nom}${suf}.png`, fullPage: opt.plein !== false });
    console.log('capture', `${conf.prefixe}${nom}${suf}.png`);
  }
  async function visite(page, hash, attente) {
    await page.goto(url(hash));
    await pret(page, attente);
  }

  /* ---------- captures de chaque page, à deux largeurs ---------- */
  async function parcours(w, h, suf) {
    const { ctx, page } = await nouveauContexte(w, h);
    const EP = '#epreuve/' + encodeURIComponent(conf.epreuve);
    const pas = conf.reel ? [
      ['01-accueil', '#/', { defile: true }],
      ['02-coureurs', '#coureurs', {}],
      ['03-courses-2018', '#courses/2018', {}],
      ['04-epreuve-tdf', EP, {}],
      ['05-coureur-pogacar', '#coureur/' + conf.coureur, {}],
      ['06-epreuve-tdf-1903', EP, { vers: '#econtent tbody tr:last-child' }],
      ['07-epreuve-tdf-records', EP, { etab: 'records' }],
      ['08-coureur-historique-garin', '#coureur/wd-Q273842', {}],
      ['09a-equipe-movistar-effectif', '#equipe/Q6175', {}],
      ['09b-equipe-movistar-mouvements', '#equipe/Q6175', { qtab: 'mouvements' }],
      ['09c-equipe-movistar-gt', '#equipe/Q6175', { qtab: 'gt' }],
      ['09d-equipe-movistar-historique', '#equipe/Q6175', { qtab: 'historique' }],
      ['09e-equipe-movistar-palmares', '#equipe/Q6175', { qtab: 'palmares' }],
      ['10-equipes-2025', '#equipes/2025', {}],
      ['11-coureur-merlier-equipes', '#coureur/' + conf.coureur2, { onglet: 'parcours' }],
    ] : [
      ['01-accueil', '#/', { defile: true }],
      ['02a-courses-resultats', '#courses/2026', {}],
      ['02b-courses-avenir', '#courses/2027?vue=avenir', {}],
      ['02c-courses-epreuves', '#courses/epreuves', {}],
      ['02d-courses-archive', '#courses/2024', {}],
      ['03a-epreuve', EP, {}],
      ['03b-epreuve-navbox-ouvert', EP, { navbox: true }],
      ['03c-epreuve-records', EP, { etab: 'records' }],
      ['07c-coureur-palmares-historique', '#coureur/demo-paul-19961228', { onglet: 'palmares' }],
      ['07d-coureur-historique', '#coureur/wd-Q99900301', {}],
      ['04a-edition-archive', '#course/fx-a24-tour-hc', {}],
      ['04b-edition-en-cours', '#course/fx-tour-test', {}],
      ['05-equipes', '#equipes', {}],
      ['05a-equipe-bravo-effectif', '#equipe/Q99900110', {}],
      ['05b-equipe-bravo-effectif-2023', '#equipe/Q99900110?s=2023', {}],
      ['05c-equipe-bravo-mouvements', '#equipe/Q99900110', { qtab: 'mouvements' }],
      ['05d-equipe-bravo-gt', '#equipe/Q99900110', { qtab: 'gt' }],
      ['05e-equipe-bravo-historique', '#equipe/Q99900110', { qtab: 'historique' }],
      ['05f-equipe-alpha-palmares', '#equipe/Q99900100', { qtab: 'palmares' }],
      ['05g-equipe-alpha-historique-navbox', '#equipe/Q99900100', { qtab: 'historique', navbox: true }],
      ['05h-equipe-saison-sans-lignee', '#equipe/charlie-team-2026', {}],
      ['05i-equipe-saison-palmares', '#equipe/golf-team-2026', { qtab: 'palmares' }],
      ['05j-equipe-selection-nationale', '#equipe/france-2024', {}],
      ['05k-equipe-introuvable', '#equipe/inconnue-2024', {}],
      ['05l-edition-participants-cliquables', '#course/fx-a24-tour-hc', { sub: 'participants' }],
      ['05n-edition-participants-effectifs', '#course/fx-a24-tour-hc', { sub: 'participants', tous: true }],
      ['05m-coureur-parcours-frise', '#coureur/epure-paul-19970711', { onglet: 'parcours' }],
      ['06a-coureurs-liste', '#coureurs', {}],
      ['06b-coureurs-francais-filtre', '#coureurs?nat=FRA', {}],
      ['06c-coureurs-vue-francais', '#coureurs?vue=francais', {}],
      ['07a-coureur', '#coureur/' + conf.coureur, {}],
      ['07b-coureur-palmares', '#coureur/' + conf.coureur, { onglet: 'palmares' }],
      ['08a-classements-uci', '#classements/uci', {}],
      ['08b-classements-saison', '#classements/uci/2024', {}],
      ['08c-classements-fdj', '#classements/fdj', {}],
      ['09-recherche', '#recherche/ebauche', {}],
    ];
    for (const [nom, hash, o] of pas) {
      try {
        await visite(page, hash);
        if (o.navbox) { const d = await page.$('details.navbox > summary'); if (d) await d.click(); }
        if (o.onglet) { const b = await page.$(`#rtabs [data-rtab="${o.onglet}"]`); if (b) await b.click(); }
        if (o.qtab) { const b = await page.$(`#qtabs [data-qtab="${o.qtab}"]`); if (b) await b.click(); }
        if (o.sub) { const b = await page.$(`#subtabs [data-sub="${o.sub}"]`); if (b) await b.click(); await page.waitForTimeout(500); }
        if (o.tous) { const b = await page.$('[data-action="part-tous"]'); if (b) await b.click(); await page.waitForTimeout(300); }
        if (o.etab) { const b = await page.$(`#etabs [data-etab="${o.etab}"]`); if (b) await b.click(); }
        if (o.vers) { await page.evaluate(sel => document.querySelector(sel).scrollIntoView({ block: 'center' }), o.vers); o.plein = false; }
        await cap(page, nom, suf, o);
      } catch (e) { echecs.push(`capture ${nom}${suf}: ${e.message}`); console.log('ECHEC capture', nom, suf, e.message); }
    }
    if (suf === '-d') {
      // menu horizontal visible, barre du bas absente ; en mobile l'inverse, zones tactiles >= 44 px
      await visite(page, '#/');
      ok('1024 px : menu horizontal visible', await page.evaluate(() => getComputedStyle(document.getElementById('dnav')).display !== 'none'));
      ok('1024 px : barre du bas masquée', await page.evaluate(() => getComputedStyle(document.getElementById('bnav')).display === 'none'));
    } else {
      await visite(page, '#/');
      ok('390 px : barre du bas visible, menu horizontal masqué', await page.evaluate(() => getComputedStyle(document.getElementById('bnav')).display !== 'none' && getComputedStyle(document.getElementById('dnav')).display === 'none'));
      const hs = await page.$$eval('#bnav a', l => l.map(a => Math.round(a.getBoundingClientRect().height)));
      ok('390 px : zones tactiles de la barre du bas >= 44 px', hs.length === 5 && hs.every(x => x >= 44), hs);
      const pos = await page.evaluate(() => { const b = document.getElementById('bnav').getBoundingClientRect(); return Math.round(window.innerHeight - b.bottom); });
      ok('390 px : barre du bas collée en bas', pos === 0, pos);
      const safe = await page.evaluate(() => getComputedStyle(document.getElementById('bnav')).paddingBottom);
      console.log('padding-bas barre (safe-area, 0 hors iPhone) :', safe);
    }
    await ctx.close();
  }
  await parcours(390, 844, '-m');
  await parcours(1024, 800, '-d');

  /* ---------- navigation, retour arrière, anciennes URL (mobile) ---------- */
  if (!conf.reel) {
    const { ctx, page } = await nouveauContexte(390, 844);
    const hash = () => page.evaluate(() => location.hash);
    const accueil = async () => ['', '#/'].includes(await hash());
    const titre = () => page.title();
    await visite(page, '#/');
    ok('accueil : titre', (await titre()) === 'Courses cyclistes', await titre());
    // carte d'un dernier résultat -> édition -> retour
    await page.evaluate(() => window.scrollTo(0, 300)); await page.waitForTimeout(150);
    const y0 = await page.evaluate(() => Math.round(window.scrollY));
    await page.click('#main .home .card.click'); await page.waitForSelector('#main .art .podium, #main .art .stage-head, #main .art .card');
    ok('carte -> #course/...', (await hash()).startsWith('#course/'), await hash());
    ok('édition : titre de document', (await titre()).endsWith('· Courses cyclistes') && (await titre()) !== 'Courses cyclistes', await titre());
    ok("édition : fil d'Ariane", (await page.$$eval('.crumbs a', l => l.map(a => a.textContent))).join('>') .startsWith('Accueil>Courses'), await page.$$eval('.crumbs a', l => l.map(a => a.textContent)));
    await page.goBack(); await page.waitForSelector('#main .home'); await page.waitForTimeout(400);
    const y1 = await page.evaluate(() => Math.round(window.scrollY));
    ok('retour -> accueil, défilement restauré', (await accueil()) && Math.abs(y1 - y0) < 40, { hash: await hash(), y0, y1 });
    // menu bas : Courses -> Épreuves -> épreuve -> coureur -> retours
    await page.click('#bnav a[data-nav="courses"]'); await pret(page);
    ok('menu Courses', (await hash()) === '#courses', await hash());
    await page.click('[data-cgo*="epreuves"]'); await pret(page, '#ep-list .crow');
    ok('vue Épreuves (replace)', (await hash()).startsWith('#courses/epreuves'), await hash());
    await page.fill('#ep-q', 'demonstration'); await page.waitForTimeout(250);
    ok('recherche épreuve filtre la liste', (await page.$$('#ep-list .crow')).length === 1, await page.$$eval('#ep-list .crow .nm', l => l.map(x => x.textContent)));
    ok('recherche épreuve dans le hash', (await hash()).includes('q=demonstration'), await hash());
    await page.click('#ep-list .crow'); await pret(page, '#main .art');
    ok('épreuve ouverte', (await hash()).startsWith('#epreuve/'), await hash());
    ok('épreuve : titre', /Omloop de/.test(await titre()), await titre());
    await page.goBack(); await pret(page, '#ep-list');
    ok('retour -> liste filtrée conservée', (await hash()).includes('q=demonstration') && (await page.$eval('#ep-q', e => e.value)) === 'demonstration', await hash());
    await page.goBack(); await pret(page, '#main .home');
    ok('retour -> accueil (le changement de vue n\'a pas créé d\'entrée d\'historique)', await accueil(), await hash());
    // filtre en page ne pollue pas l'historique : accueil -> coureurs, filtre FRA, retour = accueil
    await page.click('#bnav a[data-nav="coureurs"]'); await pret(page, '#co-list .crow');
    await page.click('[data-cgo*="nat=FRA"]'); await pret(page, '#co-list .crow');
    ok('filtre Français dans le hash', (await hash()).includes('nat=FRA'), await hash());
    const nFr = await page.$$eval('#co-list .crow', l => l.length), nTous = 0;
    ok('filtre Français : lignes FR seulement', (await page.$$('#co-list .crow:not(.fr)')).length === 0 && nFr > 0, nFr);
    await page.goBack(); await pret(page, '#main .home');
    ok("un filtre ne crée pas d'entrée d'historique", await accueil(), await hash());
    // lien profond ntfy
    await visite(page, '#course/fx-tour-test/7', '#main .art');
    ok('lien profond #course/<id>/<étape>', await page.evaluate(() => !!document.querySelector('.stage-chip.active')) && (await hash()) === '#course/fx-tour-test/7', await hash());
    // anciennes URL
    await page.goto(`http://127.0.0.1:${conf.port}/index.html?data=${conf.data}&archive=2024`); await pret(page);
    ok('ancienne URL ?archive=2024', (await hash()) === '#courses/2024' && !(await page.evaluate(() => location.search)).includes('archive'), { h: await hash(), s: await page.evaluate(() => location.search) });
    ok('?archive=2024 : saison 2024 affichée', (await page.$eval('#cs-saison', e => e.options[e.selectedIndex].text)).startsWith('2024'));
    await page.goto(`http://127.0.0.1:${conf.port}/index.html?data=${conf.data}&saison=2027`); await pret(page);
    ok('ancienne URL ?saison=2027', (await hash()) === '#courses/2027', await hash());
    // page inconnue
    await visite(page, '#nimportequoi', '#main .pg');
    ok('page introuvable', (await page.$eval('#main', e => e.textContent)).includes("n'existe pas"));
    // recherche : saisie -> hash, résultat -> coureur, retour = recherche
    await visite(page, '#recherche');
    await page.fill('#sr-q', 'paul epure'); await page.waitForSelector('#sr-body .sr-item.nav');
    ok('recherche : hash mis à jour', (await hash()) === '#recherche/paul%20epure', await hash());
    await page.click('#sr-body .sr-item.nav'); await pret(page, '#main .art');
    ok('résultat -> coureur', (await hash()).startsWith('#coureur/'), await hash());
    await page.goBack(); await page.waitForSelector('#sr-body .sr-item.nav');
    ok('retour -> recherche conservée', (await page.$eval('#sr-q', e => e.value)) === 'paul epure', await hash());
    // équipes : miroir JS de netutil.slugify (couples de docs/SPEC.md §4.5, constante encyclopedie.COUPLES_SLUG), redirection, liens
    const couples = [["Groupama - FDJ", "groupama-fdj"], ["Arkea-B&B Hotels", "arkea-b-b-hotels"], ["Team Dauner D&DQ | Akkon", "team-dauner-d-dq-akkon"],
      ["Amore E Vita | P:", "amore-e-vita-p"], ["Canel's - Java", "canel-s-java"], ["Akros - Excelsior - Thömus", "akros-excelsior-thomus"],
      ["Aviludo - Louletano - Loulé", "aviludo-louletano-loule"], ["7ELEVEN Cliqq - AIR21 by Roadbike Philippines", "7eleven-cliqq-air21-by-roadbike-philippines"],
      ["AP Hotels & Resorts /tavira/ SC Farense", "ap-hotels-resorts-tavira-sc-farense"], ["Pauwels Sauzen – Bingoal", "pauwels-sauzen-bingoal"],
      ["Lubelskie Perła Polski", "lubelskie-pera-polski"], ["RAD-NET OßWALD", "rad-net-owald"], ["Heizomat RAD-Net.de", "heizomat-rad-net-de"], ["", ""], ["---", ""]];
    await visite(page, '#/');
    const slugs = await page.evaluate(c => c.map(([n]) => slugEquipe(n)), couples);
    ok('miroir JS de netutil.slugify : couples du SPEC', couples.every(([, att], i) => slugs[i] === att), couples.map(([n, att], i) => [n, att, slugs[i]]).filter(x => x[1] !== x[2]));
    ok('id équipe-saison depuis un libellé brut', await page.evaluate(() => idEquipeSaison("Groupama - FDJ", 2025) === "groupama-fdj-2025" && idEquipeSaison("---", 2025) === null));
    await visite(page, '#equipe/bravo-cycling-2023', '#main .art');
    ok("équipe-saison d'une lignée : redirigée vers la lignée", (await hash()) === '#equipe/Q99900110?s=2023', await hash());
    ok('lignée : titre', /^Bravo Cycling/.test(await titre()), await titre());
    ok('lignée : sélecteur de saison sur 2023', (await page.$eval('#eq-an', e => e.options[e.selectedIndex].text)) === 'Saison 2023');
    await page.selectOption('#eq-an', { index: 0 }); await page.waitForTimeout(300);
    ok("changement de saison : route remplacée", (await hash()).startsWith('#equipe/Q99900110?s=') && (await page.$$('#qtabs .subtab')).length >= 3, await hash());
    ok("lignée : coureur cliquable dans l'effectif", (await page.$$('#qcontent [data-rider]')).length > 0);
    await visite(page, '#equipe/charlie-team-2026', '#main .art');
    ok('équipe-saison sans lignée : pas de redirection', (await hash()) === '#equipe/charlie-team-2026', await hash());
    ok('équipe-saison sans lignée : « Même nom en » avec liens', (await page.$$('.meme-nom a')).length >= 1, await page.$$eval('.meme-nom a', l => l.map(a => a.getAttribute('href'))));
    await visite(page, '#equipe/zzz-2024', '#main .pg');
    ok('équipe inconnue : message propre', (await page.$eval('#main', e => e.textContent)).includes('introuvable'));
    await visite(page, '#equipes', '#eq-list .crow');
    await page.click('#eq-list a.crow'); await pret(page, '#main .art');
    ok('liste des équipes -> article', (await hash()).startsWith('#equipe/'), await hash());
    await visite(page, '#course/fx-a24-tour-hc', '#main .art');
    await page.click('#subtabs [data-sub="participants"]'); await page.waitForTimeout(600);
    const liensEq = await page.$$eval('#table .team-head a.tlink', l => l.map(a => a.getAttribute('href')));
    ok("participants : titre d'équipe cliquable (équipe existante seulement)", liensEq.length > 0 && liensEq.every(h => h.startsWith('#equipe/')), liensEq);
    ok('participants : cartes repliées par défaut', (await page.$$('#table .team-card .rows')).length === 0);
    ok('participants : logo de lignée affiché (saison sous le nom actuel)', (await page.$$('#table .tc-logo img')).length > 0);
    await page.click('#table .team-card .tc-tog'); await page.waitForTimeout(200);
    ok('participants : un clic ouvre une carte', (await page.$$('#table .team-card.ouvert .rows .row')).length > 0 && (await page.$$('#table .team-card.ouvert')).length === 1);
    await page.click('[data-action="part-tous"]'); await page.waitForTimeout(200);
    ok('participants : « Effectifs » ouvre toutes les cartes', await page.$$eval('#table .team-card', l => l.length > 1 && l.every(c => c.classList.contains('ouvert'))));
    await page.click('[data-action="part-tous"]'); await page.waitForTimeout(200);
    ok('participants : « Effectifs » referme tout', (await page.$$('#table .team-card.ouvert')).length === 0);
    await visite(page, '#recherche/bravo', '#sr-body .sr-item');
    ok('recherche : équipes et lignées cliquables', (await page.$$eval('#sr-body .sr-item.nav[data-sr="l"], #sr-body .sr-item.nav[data-sr="e"]', l => l.length)) > 0);
    await page.click('#sr-body .sr-item.nav[data-sr="l"]'); await pret(page, '#main .art');
    ok('résultat lignée -> article', (await hash()).startsWith('#equipe/Q'), await hash());
    await visite(page, '#coureurs', '#co-list .crow');
    ok('annuaire : équipe cliquable', (await page.$$('#co-list .crow .tlink')).length > 0);
    // retour arrière sur coureur -> édition -> épreuve
    await visite(page, '#coureur/epure-paul-19970711', '#main .art .tile');
    await page.click('[data-rtab="palmares"]'); await page.waitForSelector('.res');
    await page.click('.res'); await pret(page, '#main .art');
    ok('palmarès -> édition', (await hash()).startsWith('#course/'), await hash());
    await page.goBack(); await page.waitForSelector('#main .art .tile');
    ok('retour -> coureur', (await hash()).startsWith('#coureur/'), await hash());
    await ctx.close();
  }

  /* ---------- mesures sur la liste des coureurs (données réelles) ---------- */
  if (conf.reel) {
    const { ctx, page } = await nouveauContexte(390, 844);
    const reponses = [];
    page.on('response', async r => { if (r.url().includes('coureurs/index.json')) { try { const b = await r.body(); reponses.push({ octets: b.length, enc: r.headers()['content-encoding'] || '' }); } catch (e) {} } });
    const t0 = Date.now();
    await page.goto(url('#coureurs'));
    await page.waitForSelector('#co-list .crow', { timeout: 60000 });
    const t1 = Date.now();
    const n = await page.evaluate(() => document.getElementById('co-count').textContent);
    console.log('MESURE liste des coureurs : première ligne affichée après', t1 - t0, 'ms ;', n, ';', JSON.stringify(reponses));
    const t2 = Date.now();
    await page.fill('#co-q', 'pogacar'); await page.waitForFunction(() => document.querySelectorAll('#co-list .crow').length > 0 && document.querySelectorAll('#co-list .crow').length < 20);
    console.log('MESURE recherche « pogacar » (saisie -> liste filtrée) :', Date.now() - t2, 'ms ;', await page.$$eval('#co-list .crow .nm', l => l.slice(0, 5).map(x => x.textContent)));
    const t3 = Date.now();
    await page.fill('#co-q', ''); await page.click('[data-cgo*="nat=FRA"]'); await page.waitForFunction(() => location.hash.includes('nat=FRA'));
    await page.waitForTimeout(100);
    console.log('MESURE filtre Français :', Date.now() - t3, 'ms ;', await page.evaluate(() => document.getElementById('co-count').textContent));
    await ctx.close();
  }

  await browser.close();
  console.log('ERREURS_CONSOLE', JSON.stringify(erreurs));
  console.log('DEBORDEMENTS', JSON.stringify(debord));
  console.log('ECHECS', JSON.stringify(echecs));
  if (echecs.length || debord.length || erreurs.length) process.exitCode = 2;
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
    ap.add_argument("--data", default="tools/fixtures/data", help="dossier de données relatif à la racine servie (jeu fictif)")
    ap.add_argument("--reel", metavar="DOSSIER", help="données réelles : dossier servi (index.html, data, archives) ; captures préfixées vrai-")
    ap.add_argument("--archives", default="archives", help="valeur de ?archives= en mode --reel")
    args = ap.parse_args()
    sortie = Path(args.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    racine = Path(args.reel) if args.reel else RACINE
    srv = serveur(racine)
    port = srv.server_address[1]
    print(f"[INFO] serveur local sur 127.0.0.1:{port} ({racine}), captures dans {sortie}")
    chromium = None
    for p in sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")):
        chromium = str(p)
    conf = {"port": port, "data": args.data, "sortie": str(sortie), "chromium": chromium, "reel": bool(args.reel),
            "archives": args.archives if args.reel else "", "prefixe": "vrai-" if args.reel else "",
            "epreuve": "tour de france|FRA" if args.reel else "grand prix de test sur mer fictif|FRA",
            "coureur": "pogacar-tadej-19980921" if args.reel else "epure-paul-19970711",
            "coureur2": "merlier-tim-19921030" if args.reel else ""}
    env = dict(os.environ, NODE_PATH=NODE_PATH, APERCU_CONF=json.dumps(conf))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(SCRIPT_NODE)
        script = f.name
    try:
        r = subprocess.run(["node", script], env=env, capture_output=True, text=True, timeout=900)
    finally:
        os.unlink(script)
    print(r.stdout)
    if r.returncode:
        print(r.stderr, file=sys.stderr)
    srv.shutdown()
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
