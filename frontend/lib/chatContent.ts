export interface ParsedVisionTable {
  title: string;
  headers: string[][];
  rows: string[][];
}

const SOURCES_TAIL_RE = /\n\nSources:\n[\s\S]*$/;

export function stripSourcesSection(text: string): string {
  return text.replace(SOURCES_TAIL_RE, "");
}

export function parseVisionTable(content: string): ParsedVisionTable {
  let headers: string[][] = [];
  let rows: string[][] = [];
  let title = "";

  for (const line of content.split("\n")) {
    const t = line.trim();
    if (t.startsWith("Title: ")) {
      title = t.slice(7);
    } else if (t.startsWith("Source: ") || t === "") {
      // skip metadata / blank lines
    } else if (t.startsWith("Headers: ")) {
      headers.push(t.slice(9).split(" | "));
    } else if (t.includes(" | ")) {
      rows.push(t.split(" | "));
    } else if (t) {
      rows.push([t]);
    }
  }

  if (headers.length > 0 && rows.length > 0) {
    const maxDataCols = Math.max(...rows.map(row => row.length));
    const maxHeaderCols = Math.max(...headers.map(header => header.length));

    if (maxDataCols > maxHeaderCols) {
      headers = headers.map(header => {
        const diff = maxDataCols - header.length;
        return diff > 0 ? [...Array(diff).fill(""), ...header] : header;
      });
    }

    if (maxHeaderCols - maxDataCols === 1) {
      const significant = rows.filter(row => row.length > 1);
      if (significant.length > 0 && significant.every(row => row.length === maxDataCols)) {
        rows = rows.map(row => row.length > 1 ? ["", ...row] : row);
      }
    }
  }

  return { title, headers, rows };
}
