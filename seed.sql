-- Insert Coracle 2026 event
INSERT INTO core_event (name, start_date, end_date, is_active, created_at, updated_at)
VALUES ('Coracle 2026', '2026-11-12', '2026-11-15', 1, datetime('now'), datetime('now'));

-- Insert ticket types tied to the event
INSERT INTO core_tickettype (event_id, name, label, description, price, stripe_price_id, max_per_user, is_restricted, created_at, updated_at)
VALUES
    ((SELECT id FROM core_event WHERE name = 'Coracle 2026'), 'adult_ticket', 'Adult Ticket', 'General admission for adults', 100, 'price_1T4U2SK9GOXEfTNqNLuPn0Av', 4, 0, datetime('now'), datetime('now')),
    ((SELECT id FROM core_event WHERE name = 'Coracle 2026'), 'child_ticket', 'Child Ticket', 'General admission for children (12 and under)', 100, 'price_1T4U2AK9GOXEfTNqqYrHAhff', 4, 0, datetime('now'), datetime('now')),
    ((SELECT id FROM core_event WHERE name = 'Coracle 2026'), 'vehicle_pass', 'Vehicle Pass', 'Parking pass for one vehicle', 100, 'price_1T4U2SK9GOXEfTNqNLuPn0Av', 2, 0, datetime('now'), datetime('now'));

-- Insert Gate role
INSERT INTO core_role (event_id, name, description, created_at, updated_at)
VALUES ((SELECT id FROM core_event WHERE name = 'Coracle 2026'), 'Gate', 'Working the entrance gate', datetime('now'), datetime('now'));

-- Insert Gate shifts (9am-5pm in 2-hour shifts, capacity 2, for each day of the event)
-- Nov 12, 2026
INSERT INTO core_shift (role_id, start_time, end_time, capacity, created_at, updated_at)
VALUES
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-12 09:00:00', '2026-11-12 11:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-12 11:00:00', '2026-11-12 13:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-12 13:00:00', '2026-11-12 15:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-12 15:00:00', '2026-11-12 17:00:00', 2, datetime('now'), datetime('now')),
    -- Nov 13, 2026
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-13 09:00:00', '2026-11-13 11:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-13 11:00:00', '2026-11-13 13:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-13 13:00:00', '2026-11-13 15:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-13 15:00:00', '2026-11-13 17:00:00', 2, datetime('now'), datetime('now')),
    -- Nov 14, 2026
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-14 09:00:00', '2026-11-14 11:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-14 11:00:00', '2026-11-14 13:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-14 13:00:00', '2026-11-14 15:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-14 15:00:00', '2026-11-14 17:00:00', 2, datetime('now'), datetime('now')),
    -- Nov 15, 2026
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-15 09:00:00', '2026-11-15 11:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-15 11:00:00', '2026-11-15 13:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-15 13:00:00', '2026-11-15 15:00:00', 2, datetime('now'), datetime('now')),
    ((SELECT id FROM core_role WHERE name = 'Gate'), '2026-11-15 15:00:00', '2026-11-15 17:00:00', 2, datetime('now'), datetime('now'));
