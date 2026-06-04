# Original Report Documents

This project uses annual report PDFs as the original source documents for the
financial retrieval and analysis pipeline. The PDFs are not committed to this
repository because they are large binary files and can be downloaded publicly
from their source locations.

To reproduce the local data setup, create a `data/reports/` directory, download
each PDF from the corresponding public URL, and save it with the exact filename
shown below. The file order follows the current order used in `data/reports/`.

After the PDFs are in place, the ingestion scripts can read them from
`data/reports/` without any additional path changes.

| File | Source download URL |
| --- | --- |
| `BHP_FY2023.pdf` | `https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file/2924-02699939-3A623777` |
| `BHP_FY2024.pdf` | `https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file/2924-02843544-3A648835` |
| `BHP_FY2025.pdf` | `https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file/2924-02980020-3A673734` |
| `FMG_FY2023.pdf` | `https://announcements.asx.com.au/asxpdf/20230828/pdf/05t4vq395zntr7.pdf` |
| `FMG_FY2024.pdf` | `https://announcements.asx.com.au/asxpdf/20240828/pdf/0674dymqjzpnvq.pdf` |
| `FMG_FY2025.pdf` | `https://content.fortescue.com/fortescue17114-fortescueeb60-productionbbdb-8be5/media/project/fortescueportal/shared/documents/regulatory/asx-announcements/2935109-fy25-annual-report-and-appendix-4e.pdf` |
| `MIN_FY2023.pdf` | `https://www.annualreports.com/HostedData/AnnualReportArchive/M/ASX_MIN_2023.pdf` |
| `MIN_FY2024.pdf` | `https://www.annualreports.com/HostedData/AnnualReports/PDF/ASX_MIN_2024.pdf` |
| `MIN_FY2025.pdf` | `https://cdn.sanity.io/files/o6ep64o3/production/44960a27514a9cc4475da34855c5995cf07a83aa.pdf` |
| `NST_FY2023.pdf` | `https://www.annualreports.com/HostedData/AnnualReportArchive/n/ASX_NST_2023.pdf` |
| `NST_FY2024.pdf` | `https://www.nsrltd.com/media/kmlbwkzn/2-2024-annual-report-double-page-22-08-2024.pdf` |
| `NST_FY2025.pdf` | `https://www.nsrltd.com/media/vemd3ef5/2-2025-annual-report-double-page-21-08-2025.pdf` |
| `RIO_FY2023.pdf` | `https://www.riotinto.com/-/media/Content/Documents/Invest/Reports/Annual-reports/RT-Annual-Report-2023.pdf` |
| `RIO_FY2024.pdf` | `https://www.riotinto.com/-/media/content/documents/invest/reports/annual-reports/2024-annual-report.pdf` |
| `RIO_FY2025.pdf` | `https://www.riotinto.com/-/media/content/documents/invest/reports/annual-reports/2025-annual-report.pdf` |

Note: some URLs point to ASX, MarkitDigital, AnnualReports, or company CDN
mirrors rather than the company investor page itself. They were the public URLs
used to retrieve the original PDFs for this project.
