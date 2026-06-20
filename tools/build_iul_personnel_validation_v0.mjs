#!/usr/bin/env node
/**
 * Harvest IUL PDF rosters as hash-only validation evidence.
 *
 * Detached .sig files are intentionally excluded. They are neither IUL content
 * nor project-document content and belong to a separate future signature layer.
 */

import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const DEFAULT_EDGES = 'E:/output/DocSpectrum/owner_identity_typed_graph_v1/owner_identity_typed_edges_v1.csv'
const DEFAULT_OBJECTS = 'E:/output/DocSpectrum/gip_control_registry_expanded_v0/gip_control_objects_v0.csv'
const DEFAULT_ARCHIVE_ROOT = 'E:/MSE_арх'
const DEFAULT_OUTPUT_DIR = 'E:/output/DocSpectrum/iul_personnel_validation_v0'
const DEFAULT_MUPDF = 'E:/Projects/OpenAI/pp87-checker_new/node_modules/mupdf/dist/mupdf.js'

export function parseCsv(text) {
  const rows = []
  let row = []
  let field = ''
  let quoted = false
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"'
        index += 1
      } else if (char === '"') {
        quoted = false
      } else {
        field += char
      }
    } else if (char === '"') {
      quoted = true
    } else if (char === ',') {
      row.push(field)
      field = ''
    } else if (char === '\n') {
      row.push(field.replace(/\r$/, ''))
      rows.push(row)
      row = []
      field = ''
    } else {
      field += char
    }
  }
  if (field || row.length) {
    row.push(field.replace(/\r$/, ''))
    rows.push(row)
  }
  const [headers, ...data] = rows.filter((values) => values.some((value) => value !== ''))
  return data.map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ''])))
}

function csvCell(value) {
  const text = value == null ? '' : String(value)
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

function writeCsv(filePath, rows, fields) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  const lines = [fields.map(csvCell).join(',')]
  for (const row of rows) lines.push(fields.map((field) => csvCell(row[field])).join(','))
  fs.writeFileSync(filePath, `\uFEFF${lines.join('\r\n')}\r\n`, 'utf8')
}

function readCsv(filePath) {
  return parseCsv(fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, ''))
}

export function isIulPdf(fileName) {
  if (path.extname(fileName).toLowerCase() !== '.pdf') return false
  return /(^|[^а-яё])(иул|уил)([^а-яё]|$)|информац.{0,20}удостовер/i.test(fileName)
}

function normalizePerson(value) {
  return value
    .toLocaleLowerCase('ru-RU')
    .replaceAll('ё', 'е')
    .replace(/[‐‑‒–—−]/g, '-')
    .replace(/\s+/g, ' ')
    .replace(/\s*\.\s*/g, '.')
    .trim()
}

function personHash(value) {
  return crypto.createHash('sha1').update(normalizePerson(value), 'utf8').digest('hex')
}

function surnameHash(value) {
  return personHash(normalizePerson(value).split(' ')[0])
}

export function classifyRole(value) {
  const role = value.toLocaleLowerCase('ru-RU').replaceAll('ё', 'е')
  if (/(^|\W)гип(\W|$)|главн.{0,12}инженер.{0,12}проекта/.test(role)) return 'gip'
  if (/разработ|исполн|проектир|составил|инженер|архитектор/.test(role)) return 'developer'
  if (/н\.?\s*контрол|нормоконтрол|проверил|согласовал/.test(role)) return 'control'
  if (/утверд|директор|руководител/.test(role)) return 'approved'
  return 'other'
}

const PERSON_PATTERNS = [
  /(?<![\p{L}])[А-ЯЁ][а-яё-]{2,}\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.(?![\p{L}])/gu,
  /(?<![\p{L}])[А-ЯЁ][а-яё-]{2,}\s+[А-ЯЁ][а-яё-]{2,}\s+[А-ЯЁ][а-яё-]{2,}(?![\p{L}])/gu,
]

function personFromLine(line) {
  const trimmed = line.trim()
  for (const pattern of PERSON_PATTERNS) {
    pattern.lastIndex = 0
    const match = pattern.exec(trimmed)
    if (match) return match[0]
  }
  if (/^[А-ЯЁ][а-яё-]{2,}$/u.test(trimmed)) return trimmed
  return ''
}

export function extractRoster(text) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
  const roster = []
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const previousRole = classifyRole(lines[index - 1] || '')
    const singlePerson = personFromLine(line)
    if (previousRole !== 'other' && singlePerson && !singlePerson.includes(' ')) {
      roster.push({
        person_hash: personHash(singlePerson),
        surname_hash: surnameHash(singlePerson),
        role_class: previousRole,
        person_key_kind: 'surname_only',
      })
    }
    const currentRole = classifyRole(line)
    const previousPerson = personFromLine(lines[index - 1] || '')
    const nextPerson = personFromLine(lines[index + 1] || '')
    if (currentRole !== 'other' && previousPerson && !nextPerson) {
      roster.push({
        person_hash: personHash(previousPerson),
        surname_hash: surnameHash(previousPerson),
        role_class: currentRole,
        person_key_kind: previousPerson.includes('.')
          ? 'surname_initials'
          : previousPerson.includes(' ')
            ? 'full_name'
            : 'surname_only',
      })
    }
    for (const pattern of PERSON_PATTERNS) {
      pattern.lastIndex = 0
      for (const match of line.matchAll(pattern)) {
        const prefix = line.slice(0, match.index).trim()
        const roleSource = prefix || lines[index - 1] || ''
        roster.push({
          person_hash: personHash(match[0]),
          surname_hash: surnameHash(match[0]),
          role_class: classifyRole(roleSource),
          person_key_kind: match[0].includes('.') ? 'surname_initials' : 'full_name',
        })
      }
    }
  }
  const unique = new Map()
  for (const item of roster) unique.set(`${item.person_hash}|${item.role_class}`, item)
  return [...unique.values()]
}

function objectIdFromFolder(name) {
  const match = name.match(/^(\d{4})[_-](?:20)?(\d{2})(?:\D|$)/)
  return match ? `${match[1]}_${match[2]}` : ''
}

function walkFiles(root) {
  const result = []
  const stack = [root]
  while (stack.length) {
    const current = stack.pop()
    let entries
    try {
      entries = fs.readdirSync(current, { withFileTypes: true })
    } catch {
      continue
    }
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name)
      if (entry.isDirectory()) stack.push(fullPath)
      else if (entry.isFile() && isIulPdf(entry.name)) result.push(fullPath)
    }
  }
  return result
}

function sha1File(filePath) {
  return crypto.createHash('sha1').update(fs.readFileSync(filePath)).digest('hex')
}

function setMetrics(left, right) {
  const intersection = new Set([...left].filter((item) => right.has(item)))
  const union = new Set([...left, ...right])
  return {
    intersection_count: intersection.size,
    jaccard: union.size ? intersection.size / union.size : 0,
    left_coverage: left.size ? intersection.size / left.size : 0,
    right_coverage: right.size ? intersection.size / right.size : 0,
  }
}

function round(value) {
  return Math.round(value * 10000) / 10000
}

async function build(options) {
  const edgeRows = readCsv(options.edges).filter((row) => row.identity_edge_type_v1 === 'owner_or_template_candidate')
  const targetOrgs = new Set(edgeRows.flatMap((row) => [row.org_left, row.org_right]))
  const objectRows = readCsv(options.objects).filter((row) => targetOrgs.has(row.effective_org_canonical))
  const objectById = new Map(objectRows.map((row) => [row.object_id, row]))

  const archiveDirs = fs.readdirSync(options.archiveRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => ({ object_id: objectIdFromFolder(entry.name), full_path: path.join(options.archiveRoot, entry.name) }))
    .filter((entry) => objectById.has(entry.object_id))

  const mupdfModule = await import(pathToFileURL(options.mupdf).href)
  const mupdf = mupdfModule.default ?? mupdfModule
  const emptyMupdfStore = mupdfModule.emptyStore ?? mupdf.emptyStore ?? (() => {})
  const inventoryRows = []
  const personEvidence = []
  const seenContent = new Set()

  for (const directory of archiveDirs.sort((a, b) => a.object_id.localeCompare(b.object_id))) {
    const object = objectById.get(directory.object_id)
    for (const filePath of walkFiles(directory.full_path).sort()) {
      const contentHash = sha1File(filePath)
      const duplicate = seenContent.has(contentHash)
      if (!duplicate) seenContent.add(contentHash)
      let pageCount = 0
      let text = ''
      let parseStatus = duplicate ? 'duplicate_content_skipped' : 'parsed'
      if (!duplicate) {
        let doc
        try {
          doc = mupdf.Document.openDocument(fs.readFileSync(filePath), 'application/pdf')
          pageCount = doc.countPages()
          for (let index = 0; index < pageCount; index += 1) {
            const page = doc.loadPage(index)
            let structuredText
            try {
              structuredText = page.toStructuredText('preserve-whitespace')
              text += `\n${structuredText.asText()}`
            } finally {
              structuredText?.destroy()
              page.destroy()
            }
          }
        } catch (error) {
          const message = String(error?.message ?? '').replace(/\s+/g, ' ').slice(0, 120)
          parseStatus = `parse_error:${error?.name ?? 'Error'}:${message}`
        } finally {
          doc?.destroy()
          emptyMupdfStore()
        }
      }
      if (parseStatus === 'parsed' && !text.trim()) {
        parseStatus = 'image_only_no_text_layer'
      }
      const roster = parseStatus === 'parsed' ? extractRoster(text) : []
      inventoryRows.push({
        object_id: directory.object_id,
        organization: object.effective_org_canonical,
        file_name: path.basename(filePath),
        file_path: filePath,
        content_sha1: contentHash,
        parse_status: parseStatus,
        page_count: pageCount,
        extracted_person_role_count: roster.length,
        gip_role_present_in_roster: roster.some((item) => item.role_class === 'gip'),
      })
      for (const item of roster) {
        personEvidence.push({
          object_id: directory.object_id,
          organization: object.effective_org_canonical,
          content_sha1: contentHash,
          person_hash: item.person_hash,
          surname_hash: item.surname_hash,
          role_class: item.role_class,
          person_key_kind: item.person_key_kind,
        })
      }
    }
  }

  const byOrgRole = new Map()
  const byOrgRoleSurname = new Map()
  for (const row of personEvidence) {
    const key = `${row.organization}|${row.role_class}`
    if (!byOrgRole.has(key)) byOrgRole.set(key, new Set())
    byOrgRole.get(key).add(row.person_hash)
    if (!byOrgRoleSurname.has(key)) byOrgRoleSurname.set(key, new Set())
    byOrgRoleSurname.get(key).add(row.surname_hash)
    const allKey = `${row.organization}|all`
    if (!byOrgRole.has(allKey)) byOrgRole.set(allKey, new Set())
    byOrgRole.get(allKey).add(row.person_hash)
    if (!byOrgRoleSurname.has(allKey)) byOrgRoleSurname.set(allKey, new Set())
    byOrgRoleSurname.get(allKey).add(row.surname_hash)
  }

  const inventoryByObject = new Map()
  const evidenceByObject = new Map()
  for (const row of inventoryRows) {
    if (!inventoryByObject.has(row.object_id)) inventoryByObject.set(row.object_id, [])
    inventoryByObject.get(row.object_id).push(row)
  }
  for (const row of personEvidence) {
    if (!evidenceByObject.has(row.object_id)) evidenceByObject.set(row.object_id, [])
    evidenceByObject.get(row.object_id).push(row)
  }
  const objectGipQcRows = objectRows.map((object) => {
    const inventory = inventoryByObject.get(object.object_id) ?? []
    const evidence = evidenceByObject.get(object.object_id) ?? []
    const expectedGip = normalizePerson(object.effective_gip ?? '')
    const expectedSurnameHash = expectedGip ? surnameHash(expectedGip) : ''
    const gipEvidence = evidence.filter((row) => row.role_class === 'gip')
    const matchingGipEvidence = expectedSurnameHash
      ? gipEvidence.filter((row) => row.surname_hash === expectedSurnameHash)
      : []
    const parsed = inventory.filter((row) => row.parse_status === 'parsed')
    const imageOnly = inventory.filter((row) => row.parse_status === 'image_only_no_text_layer')
    let status
    if (!inventory.length) status = 'no_iul_pdf'
    else if (!parsed.length && imageOnly.length) status = 'image_only_needs_ocr'
    else if (!expectedSurnameHash) status = 'missing_title_gip_reference'
    else if (!gipEvidence.length) status = 'iul_gip_role_missing'
    else if (matchingGipEvidence.length) status = 'iul_gip_matches_title_gip'
    else status = 'iul_gip_differs_from_title_gip'
    return {
      object_id: object.object_id,
      organization: object.effective_org_canonical,
      iul_pdf_count: inventory.length,
      parsed_iul_pdf_count: parsed.length,
      image_only_iul_pdf_count: imageOnly.length,
      expected_title_gip_available: Boolean(expectedSurnameHash),
      iul_gip_role_evidence_count: gipEvidence.length,
      matching_title_gip_evidence_count: matchingGipEvidence.length,
      gip_qc_status: status,
    }
  })

  const orgGipQcRows = [...targetOrgs].sort().map((organization) => {
    const rows = objectGipQcRows.filter((row) => row.organization === organization)
    const comparable = rows.filter((row) => [
      'iul_gip_matches_title_gip',
      'iul_gip_differs_from_title_gip',
      'iul_gip_role_missing',
    ].includes(row.gip_qc_status))
    const matched = rows.filter((row) => row.gip_qc_status === 'iul_gip_matches_title_gip').length
    const differed = rows.filter((row) => row.gip_qc_status === 'iul_gip_differs_from_title_gip').length
    const missingRole = rows.filter((row) => row.gip_qc_status === 'iul_gip_role_missing').length
    return {
      organization,
      object_count: rows.length,
      comparable_object_count: comparable.length,
      matched_title_gip_object_count: matched,
      differing_title_gip_object_count: differed,
      missing_iul_gip_role_object_count: missingRole,
      image_only_object_count: rows.filter((row) => row.gip_qc_status === 'image_only_needs_ocr').length,
      missing_title_gip_reference_object_count: rows.filter(
        (row) => row.gip_qc_status === 'missing_title_gip_reference',
      ).length,
      title_gip_match_ratio: comparable.length ? round(matched / comparable.length) : 0,
    }
  })

  const objectCoverage = new Map()
  for (const row of objectRows) {
    objectCoverage.set(row.effective_org_canonical, {
      total: 0,
      with_parsed_iul: new Set(),
      with_roster: new Set(),
    })
  }
  for (const row of objectRows) objectCoverage.get(row.effective_org_canonical).total += 1
  for (const row of inventoryRows) {
    if (row.parse_status === 'parsed') {
      objectCoverage.get(row.organization).with_parsed_iul.add(row.object_id)
    }
  }
  for (const row of personEvidence) {
    objectCoverage.get(row.organization).with_roster.add(row.object_id)
  }

  const overlapRows = []
  for (const edge of edgeRows) {
    const row = {
      org_left: edge.org_left,
      org_right: edge.org_right,
      source_edge_type: edge.identity_edge_type_v1,
      left_object_count: objectCoverage.get(edge.org_left)?.total ?? 0,
      right_object_count: objectCoverage.get(edge.org_right)?.total ?? 0,
      left_parsed_iul_object_count: objectCoverage.get(edge.org_left)?.with_parsed_iul.size ?? 0,
      right_parsed_iul_object_count: objectCoverage.get(edge.org_right)?.with_parsed_iul.size ?? 0,
      left_roster_object_count: objectCoverage.get(edge.org_left)?.with_roster.size ?? 0,
      right_roster_object_count: objectCoverage.get(edge.org_right)?.with_roster.size ?? 0,
    }
    for (const role of ['developer', 'gip', 'control', 'approved', 'all']) {
      const left = byOrgRole.get(`${edge.org_left}|${role}`) ?? new Set()
      const right = byOrgRole.get(`${edge.org_right}|${role}`) ?? new Set()
      const metrics = setMetrics(left, right)
      const leftSurnames = byOrgRoleSurname.get(`${edge.org_left}|${role}`) ?? new Set()
      const rightSurnames = byOrgRoleSurname.get(`${edge.org_right}|${role}`) ?? new Set()
      const surnameMetrics = setMetrics(leftSurnames, rightSurnames)
      row[`${role}_left_count`] = left.size
      row[`${role}_right_count`] = right.size
      row[`${role}_shared_count`] = metrics.intersection_count
      row[`${role}_jaccard`] = round(metrics.jaccard)
      row[`${role}_left_coverage`] = round(metrics.left_coverage)
      row[`${role}_right_coverage`] = round(metrics.right_coverage)
      row[`${role}_surname_shared_count`] = surnameMetrics.intersection_count
      row[`${role}_surname_jaccard`] = round(surnameMetrics.jaccard)
    }
    const adequateCoverage = row.left_roster_object_count > 0 && row.right_roster_object_count > 0
    row.personnel_validation_status = !adequateCoverage
      ? 'insufficient_iul_coverage'
      : row.developer_shared_count > 0
        ? 'declared_developer_exact_overlap_weak'
        : row.developer_surname_shared_count > 0
          ? 'declared_developer_surname_overlap_weak'
        : row.all_shared_count > row.gip_shared_count
          ? 'declared_non_gip_exact_overlap_weak'
          : row.all_surname_shared_count > row.gip_surname_shared_count
            ? 'declared_non_gip_surname_overlap_weak'
          : row.gip_shared_count > 0
            ? 'gip_role_overlap_higher_reliability'
            : 'no_declared_overlap_not_dispositive'
    overlapRows.push(row)
  }

  fs.mkdirSync(options.outputDir, { recursive: true })
  writeCsv(path.join(options.outputDir, 'iul_pdf_inventory_v0.csv'), inventoryRows, [
    'object_id', 'organization', 'file_name', 'file_path', 'content_sha1', 'parse_status',
    'page_count', 'extracted_person_role_count', 'gip_role_present_in_roster',
  ])
  writeCsv(path.join(options.outputDir, 'iul_person_hash_evidence_v0.csv'), personEvidence, [
    'object_id', 'organization', 'content_sha1', 'person_hash', 'surname_hash',
    'role_class', 'person_key_kind',
  ])
  writeCsv(path.join(options.outputDir, 'iul_org_personnel_overlap_v0.csv'), overlapRows, Object.keys(overlapRows[0]))
  writeCsv(path.join(options.outputDir, 'iul_object_gip_qc_v0.csv'), objectGipQcRows, Object.keys(objectGipQcRows[0]))
  writeCsv(path.join(options.outputDir, 'iul_organization_gip_qc_v0.csv'), orgGipQcRows, Object.keys(orgGipQcRows[0]))

  const payload = {
    schema_version: 'iul_personnel_validation_v0',
    generated_at: new Date().toISOString(),
    target_edge_count: edgeRows.length,
    target_organization_count: targetOrgs.size,
    target_object_count: objectRows.length,
    iul_pdf_file_count: inventoryRows.length,
    unique_iul_pdf_content_count: seenContent.size,
    parsed_iul_pdf_count: inventoryRows.filter((row) => row.parse_status === 'parsed').length,
    image_only_iul_pdf_count: inventoryRows.filter(
      (row) => row.parse_status === 'image_only_no_text_layer',
    ).length,
    detached_signature_file_count: 0,
    person_hash_evidence_count: personEvidence.length,
    parsed_iul_with_gip_role_count: inventoryRows.filter(
      (row) => row.parse_status === 'parsed' && row.gip_role_present_in_roster,
    ).length,
    parsed_iul_without_gip_role_count: inventoryRows.filter(
      (row) => row.parse_status === 'parsed' && !row.gip_role_present_in_roster,
    ).length,
    validation_status_counts: Object.fromEntries(
      [...overlapRows.reduce((counter, row) => counter.set(
        row.personnel_validation_status,
        (counter.get(row.personnel_validation_status) ?? 0) + 1,
      ), new Map()).entries()].sort(),
    ),
    gip_qc_status_counts: Object.fromEntries(
      [...objectGipQcRows.reduce((counter, row) => counter.set(
        row.gip_qc_status,
        (counter.get(row.gip_qc_status) ?? 0) + 1,
      ), new Map()).entries()].sort(),
    ),
    interpretation_rules: [
      'Only IUL PDF files are read; detached .sig files are excluded.',
      'Names are persisted only as normalized SHA1 hashes.',
      'Developer, GIP, control, approved, and all-roster overlaps are reported separately.',
      'Declared developer names are weak noisy labels in the capital-repair corpus.',
      'The GIP role is more reliable because the GIP is the legally anchored IUL signer role.',
      'No declared personnel overlap is not evidence of independent authorship.',
      'IUL overlap validates the handwriting graph and is not a model input.',
    ],
  }
  fs.writeFileSync(path.join(options.outputDir, 'iul_personnel_validation_v0.json'), JSON.stringify(payload, null, 2), 'utf8')
  return payload
}

function parseArgs(argv) {
  const options = {
    edges: DEFAULT_EDGES,
    objects: DEFAULT_OBJECTS,
    archiveRoot: DEFAULT_ARCHIVE_ROOT,
    outputDir: DEFAULT_OUTPUT_DIR,
    mupdf: DEFAULT_MUPDF,
  }
  for (let index = 2; index < argv.length; index += 2) {
    const key = argv[index]
    const value = argv[index + 1]
    if (key === '--edges') options.edges = value
    else if (key === '--objects') options.objects = value
    else if (key === '--archive-root') options.archiveRoot = value
    else if (key === '--output-dir') options.outputDir = value
    else if (key === '--mupdf') options.mupdf = value
    else throw new Error(`Unknown argument: ${key}`)
  }
  return options
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  build(parseArgs(process.argv)).then((payload) => {
    console.log(JSON.stringify(payload, null, 2))
  }).catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
}
