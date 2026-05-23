// MongoDB seed script — run with: mongosh < seed-agents.js
// Or: mongosh mongodb://localhost:27017/call-service seed-agents.js

use('call-service');

db.agents.drop();

db.agents.insertMany([
  { name: 'Sarah Johnson', isAvailable: true, currentCallId: null },
  { name: 'Marcus Williams', isAvailable: true, currentCallId: null },
  { name: 'Jade Patel', isAvailable: true, currentCallId: null },
  { name: 'Alex Chen', isAvailable: true, currentCallId: null },
  { name: 'Chloe Thompson', isAvailable: true, currentCallId: null },
  { name: 'David Kim', isAvailable: true, currentCallId: null },
  { name: 'Nadia Okafor', isAvailable: true, currentCallId: null },
  { name: 'Ryan Martinez', isAvailable: true, currentCallId: null }
]);

print('✓ Seeded 8 agents into call-service.agents');
print('  Agents:', db.agents.countDocuments(), 'total');
