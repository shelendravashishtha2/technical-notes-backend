# Frontend Integration Notes

Your current React app imports:

```js
import { curatedNotes, groupOrderPreference } from './data/notes.js';
```

The backend is designed to replace that import with one bootstrap call.

## Step 1: API client

```js
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function request(path, options) {
  const res = await fetch(`${API_BASE_URL}${path}`, options);
  if (!res.ok) throw new Error(`API failed: ${res.status}`);
  return res.json();
}

export const notesApi = {
  bootstrap: () => request('/api/v1/bootstrap'),
  topic: (id) => request(`/api/v1/topics/${encodeURIComponent(id)}`),
  hydrate: (ids) => request('/api/v1/topics/hydrate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids, include_sections: true, include_sources: true, include_section_bodies: true })
  }),
  search: (q) => request(`/api/v1/search?q=${encodeURIComponent(q)}&limit=20`)
};
```

## Step 2: bootstrap state

```js
const [allTopics, setAllTopics] = useState([]);
const [groupOrderPreference, setGroupOrderPreference] = useState([]);
const [topicContentById, setTopicContentById] = useState({});

useEffect(() => {
  notesApi.bootstrap().then((payload) => {
    setAllTopics(payload.topics || []);
    setGroupOrderPreference(payload.groupOrderPreference || []);
  });
}, []);
```

## Step 3: hydrate selected topic

```js
async function ensureTopicContent(topicId) {
  if (topicContentById[topicId]?.content) return topicContentById[topicId];

  const topic = await notesApi.topic(topicId);
  setTopicContentById((prev) => ({ ...prev, [topicId]: topic }));
  return topic;
}
```

## Step 4: use cached full topic

```js
const activeTopicMeta = allTopics.find((topic) => topic.id === activeId) || allTopics[0];
const activeTopic = {
  ...activeTopicMeta,
  ...(topicContentById[activeTopicMeta?.id] || {})
};
```

## Step 5: export/full-scroll optimization

Before exporting or entering full-scroll mode, batch hydrate missing topics:

```js
async function hydrateMissingTopics(ids) {
  const missing = ids.filter((id) => !topicContentById[id]?.content);
  if (!missing.length) return;

  const topics = await notesApi.hydrate(missing);
  setTopicContentById((prev) => {
    const next = { ...prev };
    topics.forEach((topic) => { next[topic.id] = topic; });
    return next;
  });
}
```
