/**
 * Document List: Display area for uploaded documents and their processing
 * status.
 */
import { type Document } from "@/lib/api";
import { formatFileSize, formatDate } from "@/lib/utils";

interface DocumentListProps {
  documents: Document[];
  onDocumentClick: (document: Document) => void;
}

/**
 * Renders list of clickable documents. Clicking opens ChatWindow component.
 */
export function DocumentList({ documents, onDocumentClick }: DocumentListProps) {
  const getStatusColor = (status: Document["status"]) => {
    switch (status) {
      case "completed":
        return "text-green-400 bg-green-900/20";
      case "processing":
        return "text-yellow-400 bg-yellow-900/20";
      case "failed":
        return "text-red-400 bg-red-900/20";
      default:
        return "text-zinc-400 bg-zinc-800/50";
    }
  };

  if (documents.length === 0) {
    return (
      <div className="text-center py-12 text-zinc-500">
        No documents yet. Upload a PDF to get started.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {documents.map((doc) => (
        <div
          key={doc.id}
          onClick={() => onDocumentClick(doc)}
          className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-lapis-500/50 hover:bg-zinc-800/50 transition-colors cursor-pointer"
        >
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <h3 className="text-zinc-100 font-medium mb-1">{doc.filename}</h3>
              <div className="flex items-center gap-3 text-sm text-zinc-400">
                <span>{formatFileSize(doc.file_size)}</span>
                <span>•</span>
                <span>{formatDate(doc.uploaded_at)}</span>
              </div>
            </div>
            <span
              className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(doc.status)}`}
            >
              {doc.status}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
