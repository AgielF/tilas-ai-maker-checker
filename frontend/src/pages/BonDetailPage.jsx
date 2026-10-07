import { useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import WorkbenchTemplate from '../components/templates/WorkbenchTemplate';
import NavBar from '../components/organisms/NavBar';
import PageHeader from '../components/organisms/PageHeader';
import Table from '../components/atoms/Table';
import Icon from '../components/atoms/Icon';
import Button from '../components/atoms/Button';
import EmptyState from '../components/molecules/EmptyState';
import { useDocumentDetail } from '../hooks/useApi';

const formatDate = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('id-ID', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

function ItemRow({ item }) {
  return (
    <tr className="border-b border-[var(--border-dark)] last:border-0">
      <td className="px-4 py-3 font-mono tabular-nums text-[var(--color-text-inv)]">
        {item.no}
      </td>
      <td className="px-4 py-3 text-[var(--color-text-inv)]">
        {item.nama_barang}
      </td>
      <td className="px-4 py-3 font-mono tabular-nums text-right text-[var(--color-text-inv)]">
        {item.qty != null ? item.qty.toLocaleString('id-ID') : '—'}
      </td>
      <td className="px-4 py-3 text-[var(--color-text-inv)]">
        {item.satuan || '—'}
      </td>
      <td className="px-4 py-3 text-[var(--color-text-inv-mute)] max-w-md truncate">
        {item.keterangan || '—'}
      </td>
    </tr>
  );
}

export default function BonDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, loading, error } = useDocumentDetail(id);

  const handleBack = useCallback(() => {
    navigate('/bons');
  }, [navigate]);

  if (loading) {
    return (
      <WorkbenchTemplate
        navbar={<NavBar activePath="/bons" />}
        header={
          <PageHeader
            title="Detail BON"
            subtitle="Memuat detail dokumen…"
          />
        }
        resultZone={
          <div className="flex items-center justify-center gap-3 py-12 text-[var(--color-text-inv-mute)]">
            <span className="inline-block w-5 h-5 rounded-full border-2 border-electric border-r-transparent animate-spin" />
            <span className="text-sm">Memuat detail BON…</span>
          </div>
        }
      />
    );
  }

  if (error) {
    return (
      <WorkbenchTemplate
        navbar={<NavBar activePath="/bons" />}
        header={
          <PageHeader
            title="Detail BON"
            subtitle="Gagal memuat data"
          />
        }
        resultZone={
          <div className="flex items-start gap-3 border border-sev-critical/30 bg-sev-critical/5 px-4 py-4 text-sev-critical">
            <span className="text-sm">{String(error)}</span>
          </div>
        }
      />
    );
  }

  if (!data) {
    return (
      <WorkbenchTemplate
        navbar={<NavBar activePath="/bons" />}
        header={
          <PageHeader
            title="Detail BON"
            subtitle="Dokumen tidak ditemukan"
          />
        }
        resultZone={
          <EmptyState
            label="BON tidak ditemukan"
            description="BON dengan ID tersebut tidak ada di sistem."
          />
        }
      />
    );
  }

  const doc = data;

  return (
    <WorkbenchTemplate
      navbar={<NavBar activePath="/bons" />}
      header={
        <PageHeader
          title={`BON #{doc.doc_number}`}
          subtitle={`Division: ${doc.division} • ${formatDate(doc.created_at)}`}
          badge={{ label: doc.doc_type, variant: 'electric' }}
        />
      }
      inputZone={
        <div className="flex flex-col gap-4">
          {/* Metadata Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetadataCard label="BON Number" value={doc.doc_number} icon="file-text" />
            <MetadataCard label="Tanggal" value={doc.doc_date || '—'} icon="calendar" />
            <MetadataCard label="Division" value={doc.division || '—'} icon="building" />
            <MetadataCard label="File Asal" value={doc.source_file} icon="file-text" />
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-[var(--border-dark)] pb-4">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-[var(--color-text-inv-mute)]">Created:</span>
                <span className="font-mono tabular-nums text-[var(--color-text-inv)]">
                  {formatDate(doc.created_at)}
                </span>
              </div>
              <Button variant="ghost" size="sm" onClick={handleBack}>
                <Icon name="arrow-left" size={16} className="mr-1" />
                Kembali ke Arsip
              </Button>
            </div>

            {/* Items Table */}
            <div className="rounded-md border border-[var(--border-dark)] overflow-hidden">
              <Table>
                <thead>
                  <tr className="border-b border-[var(--border-dark)] bg-surface">
                    {['No', 'Nama Barang', 'Qty', 'Satuan', 'Keterangan'].map((h) => (
                      <th
                        key={h}
                        className={`${h === 'Nama Barang' || h === 'Keterangan' ? 'text-left' : 'text-right'} px-4 py-3 text-xs font-medium uppercase tracking-wider text-[var(--color-text-inv-mute)]`}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(doc.items || []).length > 0 ? (
                    doc.items.map((item, index) => (
                      <ItemRow key={item.no || `item-${index}`} item={item} />
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-[var(--color-text-inv-mute)]">
                        Tidak ada item pada BON ini.
                      </td>
                    </tr>
                  )}
                </tbody>
              </Table>
            </div>
          </div>
        </div>
      }
    />
  );
}

function MetadataCard({ label, value, icon }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border border-[var(--border-dark)] rounded-md bg-surface">
      <span className="text-electric shrink-0">
        <Icon name={icon} size={20} strokeWidth={1.5} />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-inv-mute)]">
          {label}
        </p>
        <p className="text-sm font-mono tabular-nums text-[var(--color-text-inv)] truncate">
          {value}
        </p>
      </div>
    </div>
  );
}