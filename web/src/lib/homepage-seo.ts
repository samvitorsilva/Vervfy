import type { Language } from "@/lib/language";

export const homepageSeo: Record<Language, { title: string; description: string }> = {
  "en": {
    "title": "Vervfy – Personal Music Player & Online MP3 Library",
    "description": "With Vervfy, play your own MP3s online or download them for offline listening. Manage playlists and favorites, with lyrics and artist information when available."
  },
  "pt-BR": {
    "title": "Vervfy – Player de música pessoal e biblioteca MP3 online",
    "description": "Com o Vervfy, ouça seus MP3s online ou baixe-os para ouvir offline. Organize playlists e favoritos, com letras e informações sobre artistas quando disponíveis."
  },
  "fr": {
    "title": "Vervfy – Lecteur musical personnel et bibliothèque MP3 en ligne",
    "description": "Avec Vervfy, écoutez vos MP3 en ligne ou téléchargez-les pour une écoute hors ligne. Gérez playlists et favoris, avec paroles et informations sur les artistes si disponibles."
  },
  "es": {
    "title": "Vervfy – Reproductor de música personal y biblioteca MP3 online",
    "description": "Con Vervfy, escucha tus MP3 online o descárgalos para escucharlos sin conexión. Organiza listas y favoritos, con letras e información de artistas cuando estén disponibles."
  }
};

export const homepageFeatures: Record<Language, string[]> = {
  "en": [
    "Personal music library with album artwork and song metadata",
    "Upload and play your own MP3 files online",
    "Download uploaded songs in this browser for offline playback",
    "Playlists and favorites",
    "Synchronized or plain lyrics when available",
    "Artist information when available"
  ],
  "pt-BR": [
    "Biblioteca pessoal com capas de álbuns e metadados das músicas",
    "Envie e ouça seus próprios arquivos MP3 online",
    "Baixe as músicas enviadas neste navegador para ouvir offline",
    "Playlists e favoritos",
    "Letras sincronizadas ou simples quando disponíveis",
    "Informações sobre artistas quando disponíveis"
  ],
  "fr": [
    "Bibliothèque personnelle avec pochettes et métadonnées musicales",
    "Importez et écoutez vos propres fichiers MP3 en ligne",
    "Téléchargez les morceaux importés dans ce navigateur pour une écoute hors ligne",
    "Playlists et favoris",
    "Paroles synchronisées ou simples si disponibles",
    "Informations sur les artistes si disponibles"
  ],
  "es": [
    "Biblioteca personal con portadas y metadatos de canciones",
    "Sube y reproduce tus propios archivos MP3 online",
    "Descarga las canciones subidas en este navegador para escucharlas sin conexión",
    "Listas y favoritos",
    "Letras sincronizadas o simples cuando estén disponibles",
    "Información de artistas cuando esté disponible"
  ]
};
