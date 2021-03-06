CREATE OR REPLACE FUNCTION update_user_ts() RETURNS trigger AS $$
  BEGIN
    UPDATE users SET active_ts=now() WHERE id=NEW.user_id;
    return NULL;
  END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_user_ts ON actions;
CREATE TRIGGER update_user_ts AFTER INSERT ON actions FOR EACH ROW EXECUTE PROCEDURE update_user_ts();

-- TODO can be removed once run.
DROP TRIGGER IF EXISTS ticket_insert ON tickets;

CREATE OR REPLACE FUNCTION check_tickets_remaining(event_id INT, ttl INT) RETURNS INT AS $$
  DECLARE
    tickets_taken_ INT;
  BEGIN
    DELETE FROM tickets
    WHERE status='reserved' AND event=event_id AND now() - created_ts > (ttl || ' seconds')::interval;

    SELECT coalesce(COUNT(*), 0) INTO tickets_taken_
    FROM tickets
    WHERE event=event_id AND status != 'cancelled';

    UPDATE events SET tickets_taken=tickets_taken_ WHERE id=event_id;

    return (SELECT ticket_limit - tickets_taken FROM events WHERE id=event_id);
  END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION full_name(first_name VARCHAR(255), last_name VARCHAR(255),
    email VARCHAR(255)) RETURNS VARCHAR(255) AS $$
  DECLARE
  BEGIN
    return coalesce(first_name || ' ' || last_name, first_name, last_name, email);
  END;
$$ LANGUAGE plpgsql;
