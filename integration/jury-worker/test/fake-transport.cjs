'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../public');
const fixtures = JSON.parse(fs.readFileSync(path.join(root, 'assets/fixtures.json'), 'utf8'));
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const check = value => {
  if (!value) throw new Error('Synthetic fixture contract failed');
  return value;
};

const reasons = {
  ACCEPT_ORIGINAL: ['Technische Demonstrationsschwellen erfüllt. Katzenmotiv und Identität müssen Menschen prüfen.'],
  ENHANCE: ['Mittlere Helligkeit unter 90: vorsichtige Aufhellung vorschlagen.'],
  TRY_NEXT_IMAGE: ['Stark unscharf: Laplace-Varianz unter 35; keine künstliche Rettung.', 'Sehr geringer Kontrast; zuverlässige Details fehlen.']
};

class FakeTransport {
  constructor() {
    this.calls = [];
    this.objects = new Map();
    this.sequence = 0;
    this.kind = 'iam-user';
    this.redirect = false;
  }

  async identity() {
    return {kind: this.kind, root: this.kind === 'root', region: 'eu-central-1'};
  }

  async invoke(event) {
    this.calls.push(event.operation);
    let result;
    if (event.operation === 'create') {
      this.id = (++this.sequence).toString(16).padStart(32, '0');
      this.descriptors = event.uploads;
      result = {
        job_id: this.id,
        published: false,
        uploads: event.uploads.map((photo, index) => ({
          method: 'PUT',
          expires_in: 120,
          url: 'private-fake-upload-' + index,
          headers: {
            'Content-Type': photo.content_type,
            'Content-Length': String(photo.size),
            'If-None-Match': '*',
            'x-amz-checksum-sha256': Buffer.from(photo.sha256, 'hex').toString('base64'),
            'x-amz-server-side-encryption': 'AES256'
          }
        }))
      };
    } else if (event.operation === 'analyze') {
      const items = this.descriptors.map((photo, index) => {
        const fixture = check(fixtures[photo.sha256]);
        const original = `originals/${this.id}/${index}.${photo.content_type === 'image/png' ? 'png' : 'jpg'}`;
        const proposal = fixture.action === 'ENHANCE' ? `derivatives/${this.id}/${index}.png` : original;
        if (fixture.proposal) this.objects.set(proposal, fs.readFileSync(path.join(root, fixture.proposal)));
        return {
          index,
          original,
          original_sha256: photo.sha256,
          proposal,
          proposal_sha256: fixture.proposal_sha256 || photo.sha256,
          metrics: fixture.metrics,
          after: fixture.after,
          action: fixture.action,
          eligible: fixture.action !== 'TRY_NEXT_IMAGE',
          reasons: reasons[fixture.action]
        };
      });
      const {CAT_MODEL, CAT_POLICY} = await import('../cat-contract.mjs');
      for (const item of items) {
        const simulated = metrics => {
          const bbox = [Math.floor(metrics.width * .2), Math.floor(metrics.height * .2), Math.floor(metrics.width * .8), Math.floor(metrics.height * .8)];
          const detection = {bbox, confidence: .9, area_fraction: .36, center_offset: 0, edge_contact: false};
          return {detected: true, count: 1, detections: [detection], ...detection, visibility: 'HUMAN_REVIEW_REQUIRED', crop: null, crop_resolution: null, reason: 'CAT_FRAME_OK', action: 'ACCEPT_ORIGINAL'};
        };
        item.cat = simulated(item.metrics);
        if (item.after) item.after_cat = simulated(item.after);
      }
      const selected = items.findIndex(item => item.eligible);
      this.trace = {
        cat_policy: CAT_POLICY,
        cat_model: CAT_MODEL,
        id: this.id,
        opencv_version: '5.0.0',
        items,
        selected: selected < 0 ? null : selected,
        decision: selected < 0 ? 'REQUEST_NEW_PHOTO' : items[selected].action,
        status: 'AWAITING_HUMAN',
        published: false
      };
      result = this.trace;
    } else if (event.operation === 'result') {
      const item = this.trace.items[this.trace.selected];
      result = {trace: this.trace, approval: null, published: false, previews: item ? [{url: item.original, expires_in: 60}, {url: item.proposal, expires_in: 60}] : []};
    } else if (event.operation === 'decide') {
      result = {published: false, status: event.decision === 'APPROVE' ? 'APPROVED_PRIVATE' : 'REQUEST_NEW_PHOTO', proposal_sha256: this.trace.items[this.trace.selected]?.proposal_sha256 || null};
    } else {
      throw new Error('UNKNOWN_ACTION');
    }
    return {statusCode: 200, opencv_version: '5.0.0', result: structuredClone(result)};
  }

  async upload(_url, _headers, data, key) {
    this.calls.push('upload');
    if (this.redirect) throw new Error('PRIVATE_TRANSPORT_FAILED');
    check(!this.objects.has(key));
    this.objects.set(key, Buffer.from(data));
  }

  async preview(_url, key) {
    this.calls.push('preview');
    check(this.objects.has(key));
    return Buffer.from(this.objects.get(key));
  }
}

function input(names) {
  return {
    rights: true,
    photos: names.map(name => {
      const bytes = fs.readFileSync(path.join(root, 'assets', name + '.png'));
      return {type: 'image/png', sha256: sha(bytes), base64: bytes.toString('base64')};
    })
  };
}

module.exports = {FakeTransport, input};

