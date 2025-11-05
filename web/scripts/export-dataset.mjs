import fs from 'fs-extra';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const webRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(webRoot, '..');

const DATASET_ROOT = process.env.DATASET_ROOT
  ? path.resolve(repoRoot, process.env.DATASET_ROOT)
  : path.resolve(repoRoot, 'dataset');
const OUTPUT_ROOT = path.resolve(webRoot, 'public', 'data');
const CLUSTER_FILENAME = 'arxiv_clustering_results.json';

const isDateDir = (name) => /^\d{4}-\d{2}-\d{2}$/.test(name);

const collectDateDirs = async () => {
  if (!(await fs.pathExists(DATASET_ROOT))) {
    return [];
  }

  const entries = await fs.readdir(DATASET_ROOT, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isDirectory() && isDateDir(entry.name))
    .map((entry) => entry.name)
    .sort((a, b) => b.localeCompare(a));
};

const exportDataset = async () => {
  const dates = await collectDateDirs();

  await fs.emptyDir(OUTPUT_ROOT);

  const publishedDates = [];
  for (const date of dates) {
    const sourceFile = path.join(DATASET_ROOT, date, CLUSTER_FILENAME);
    if (!(await fs.pathExists(sourceFile))) {
      continue;
    }

    const targetDir = path.join(OUTPUT_ROOT, date);
    await fs.ensureDir(targetDir);
    await fs.copyFile(sourceFile, path.join(targetDir, CLUSTER_FILENAME));

    publishedDates.push(date);
  }

  await fs.writeJson(
    path.join(OUTPUT_ROOT, 'index.json'),
    { dates: publishedDates },
    { spaces: 2 }
  );

  console.log(
    `Exported ${publishedDates.length} dataset(s) to ${path.relative(webRoot, OUTPUT_ROOT)}`
  );
};

exportDataset().catch((error) => {
  console.error('[export-dataset] Failed to export dataset:', error);
  process.exitCode = 1;
});
