import { apiClient } from "./apiClient";

// Acest client vorbeste cu files-service (prin Gateway). Separat de
// conversationService (history-service) si generateService (chat-service):
// fiecare fisier-serviciu mapeaza pe un singur microserviciu.
const SERVICE = "files-service";

export const fileService = {
  // Urca un fisier intr-o conversatie. Construim un FormData cu campul "file";
  // numele "file" trebuie sa fie identic cu parametrul UploadFile din backend
  // (POST /conversations/{conv_id}/files). Raspuns: { file_id, chunks, ... }.
  upload: (conversationId, file) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.postFormData(
      SERVICE,
      `conversations/${conversationId}/files`,
      formData
    );
  },

  // Lista fisierelor deja urcate intr-o conversatie. Backend-ul filtreaza
  // dupa user_id (din JWT) + conversation_id, deci primim doar fisierele
  // noastre. Raspuns: [{ file_id, original_name, size_bytes, mime_type, created_at }].
  list: (conversationId) =>
    apiClient.get(SERVICE, `conversations/${conversationId}/files`),

  // Sterge un fisier (binar din S3 + metadata din DB, cu cascade pe chunks).
  remove: (fileId) => apiClient.delete(SERVICE, `files/${fileId}`),

  // Descarca / previzualizeaza un fisier. Nu putem folosi un link simplu sau
  // window.open pe URL-ul Gateway-ului, pentru ca o navigare de browser nu
  // poate atasa header-ul Authorization (JWT) → ar primi 401. De aceea:
  //   1. fetch cu token → primim binarul ca Blob
  //   2. URL.createObjectURL face un URL local temporar (blob:...) pentru el
  //   3. il deschidem in tab nou; browserul randeaza PDF/text sau ofera download
  //   4. eliberam URL-ul dupa un minut ca sa nu tinem memoria ocupata
  download: async (fileId) => {
    const blob = await apiClient.getBlob(SERVICE, `files/${fileId}/download`);
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  },
};
