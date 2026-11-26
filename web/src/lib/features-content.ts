import type { Language } from "@/lib/language";

type FeaturesContent = {
  title: string;
  description: string;
  heading: string;
  intro: string;
  link: string;
  sections: readonly (readonly [string, string])[];
};

export const featuresContent: Record<Language, FeaturesContent> = {
  en: {
    title: "Music library features",
    description: "Explore Vervfy: upload your music, build playlists, save favorites, follow lyrics and download tracks for offline listening in this browser.",
    heading: "Your music, with room to make it yours.",
    intro: "Vervfy brings your own audio collection into a personal web music library. Here is what you can do once you create an account and upload your tracks.",
    link: "Explore Vervfy features",
    sections: [
      ["Bring your own music", "Upload your audio files, including MP3s. Vervfy reads song tags and embedded artwork to help organize your library. Each account has its own separate collection."],
      ["Set the pace of playback", "Play, pause, seek and skip tracks. Use the queue to see what is next, or change the flow with shuffle and repeat."],
      ["Build playlists for the moment", "Create and name playlists, add tracks from your library and remove them when your plans change."],
      ["Keep favorites close", "Save tracks to your liked songs and return to them from the favorites view."],
      ["Follow the words", "Read synchronized lyrics that follow playback when timed lyrics are available, or view plain lyrics. Vervfy can use embedded lyrics, saved custom lyrics or optional LRCLIB lookups; matches are not available for every song."],
      ["Find more about the artist", "Open an artist profile to read a biography when information is available. Artist details depend on available records and lookups, so some profiles may have no biography."],
      ["Save tracks for offline listening", "Choose Download for offline on a track while connected. Saved audio stays in this browser on this device, subject to available browser storage. Unsaved tracks and online lookups still need a connection; clearing browser data removes local downloads."],
    ],
  },
  "pt-BR": {
    title: "Recursos da biblioteca de música",
    description: "Explore o Vervfy: envie músicas, crie playlists, salve favoritos, acompanhe letras e baixe faixas para ouvir offline neste navegador.",
    heading: "Sua música, com espaço para o seu jeito.",
    intro: "O Vervfy reúne seus próprios arquivos de áudio em uma biblioteca pessoal na web. Veja o que você pode fazer ao criar uma conta e enviar suas faixas.",
    link: "Explore os recursos do Vervfy",
    sections: [
      ["Traga suas próprias músicas", "Envie seus arquivos de áudio, incluindo MP3s. O Vervfy lê as tags das músicas e as capas incorporadas para ajudar a organizar sua biblioteca. Cada conta tem sua própria coleção separada."],
      ["Escolha o ritmo da reprodução", "Reproduza, pause, avance, volte e pule faixas. Veja o que vem a seguir na fila ou mude a sequência com os modos aleatório e de repetição."],
      ["Crie playlists para cada momento", "Crie e nomeie playlists, adicione faixas da sua biblioteca e remova-as quando seus planos mudarem."],
      ["Tenha seus favoritos por perto", "Salve faixas nas músicas curtidas e volte a elas pela seção de favoritos."],
      ["Acompanhe as letras", "Leia letras sincronizadas com a reprodução quando houver marcações de tempo ou veja letras simples. O Vervfy pode usar letras incorporadas, letras personalizadas salvas ou buscas opcionais no LRCLIB; nem toda música tem uma correspondência."],
      ["Saiba mais sobre o artista", "Abra o perfil de um artista para ler uma biografia quando houver informações. Os detalhes dependem dos registros e das buscas disponíveis, por isso alguns perfis podem não ter biografia."],
      ["Salve faixas para ouvir offline", "Escolha Baixar para ouvir sem internet em uma faixa enquanto estiver conectado. O áudio salvo fica neste navegador e dispositivo, sujeito ao espaço disponível. Faixas não salvas e buscas online precisam de conexão; limpar os dados do navegador remove os downloads locais."],
    ],
  },
  fr: {
    title: "Fonctionnalités de la bibliothèque musicale",
    description: "Découvrez Vervfy : importez votre musique, créez des playlists, gardez vos favoris, suivez les paroles et écoutez vos téléchargements hors ligne dans ce navigateur.",
    heading: "Votre musique, à votre façon.",
    intro: "Vervfy réunit vos propres fichiers audio dans une bibliothèque musicale personnelle sur le web. Découvrez ce que vous pouvez faire après avoir créé un compte et importé vos morceaux.",
    link: "Découvrir les fonctionnalités de Vervfy",
    sections: [
      ["Importez votre musique", "Importez vos fichiers audio, dont vos MP3. Vervfy lit les métadonnées et les pochettes intégrées pour vous aider à organiser votre bibliothèque. Chaque compte possède sa propre collection séparée."],
      ["Choisissez le rythme de lecture", "Lancez, mettez en pause, avancez dans un morceau ou passez au suivant. Consultez la file d’attente ou changez l’ordre avec la lecture aléatoire et la répétition."],
      ["Créez des playlists pour chaque moment", "Créez et nommez des playlists, ajoutez des morceaux de votre bibliothèque et retirez-les selon vos envies."],
      ["Gardez vos favoris à portée de main", "Ajoutez des morceaux à vos titres aimés et retrouvez-les dans la vue des favoris."],
      ["Suivez les paroles", "Lisez les paroles synchronisées avec la lecture quand elles sont minutées, ou consultez les paroles simples. Vervfy peut utiliser des paroles intégrées, des paroles personnalisées enregistrées ou des recherches facultatives sur LRCLIB ; tous les morceaux n’ont pas de résultat."],
      ["Découvrez l’artiste", "Ouvrez le profil d’un artiste pour lire sa biographie lorsque des informations sont disponibles. Ces détails dépendent des données et des recherches disponibles ; certains profils peuvent ne pas avoir de biographie."],
      ["Enregistrez des morceaux pour une écoute hors ligne", "Choisissez Télécharger pour écouter hors ligne sur un morceau lorsque vous êtes connecté. L’audio reste dans ce navigateur, sur cet appareil, selon l’espace disponible. Les morceaux non enregistrés et les recherches en ligne nécessitent une connexion ; effacer les données du navigateur supprime les téléchargements locaux."],
    ],
  },
  es: {
    title: "Funciones de la biblioteca musical",
    description: "Descubre Vervfy: sube tu música, crea listas, guarda favoritos, sigue las letras y descarga canciones para escucharlas sin conexión en este navegador.",
    heading: "Tu música, con espacio para hacerla tuya.",
    intro: "Vervfy reúne tus propios archivos de audio en una biblioteca musical personal en la web. Descubre qué puedes hacer al crear una cuenta y subir tus canciones.",
    link: "Explora las funciones de Vervfy",
    sections: [
      ["Trae tu propia música", "Sube tus archivos de audio, incluidos los MP3. Vervfy lee las etiquetas de las canciones y las portadas integradas para ayudarte a organizar tu biblioteca. Cada cuenta tiene su propia colección separada."],
      ["Elige el ritmo de reproducción", "Reproduce, pausa, busca un momento y salta canciones. Consulta qué viene después en la cola o cambia el orden con los modos aleatorio y de repetición."],
      ["Crea listas para cada momento", "Crea y nombra listas de reproducción, añade canciones de tu biblioteca y elimínalas de la lista cuando cambien tus planes."],
      ["Ten tus favoritos a mano", "Guarda canciones entre tus favoritas y vuelve a ellas desde la vista de favoritos."],
      ["Sigue las letras", "Lee letras sincronizadas con la reproducción cuando tengan marcas de tiempo, o consulta letras sin sincronizar. Vervfy puede usar letras integradas, letras personalizadas guardadas o búsquedas opcionales en LRCLIB; no todas las canciones tienen resultados."],
      ["Conoce al artista", "Abre el perfil de un artista para leer su biografía cuando haya información. Los detalles dependen de los registros y las búsquedas disponibles, por lo que algunos perfiles pueden no tener biografía."],
      ["Guarda canciones para escucharlas sin conexión", "Elige Descargar para escuchar sin conexión en una canción mientras estés conectado. El audio queda en este navegador y dispositivo, sujeto al espacio disponible. Las canciones no guardadas y las búsquedas online necesitan conexión; borrar los datos del navegador elimina las descargas locales."],
    ],
  },
};
