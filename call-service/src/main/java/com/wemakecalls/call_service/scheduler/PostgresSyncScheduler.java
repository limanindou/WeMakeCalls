package com.wemakecalls.call_service.scheduler;

import com.wemakecalls.call_service.models.CallSession;
import com.wemakecalls.call_service.models.CallStatus;
import com.wemakecalls.call_service.repositories.CallRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.sql.Timestamp;
import java.util.List;

/**
 * Syncs completed call sessions from MongoDB to PostgreSQL every 10 minutes.
 * Only syncs calls that have status=COMPLETED and haven't been synced yet.
 */
@Component
public class PostgresSyncScheduler {

    private static final Logger log = LoggerFactory.getLogger(PostgresSyncScheduler.class);

    private final CallRepository callRepository;
    private final JdbcTemplate jdbcTemplate;

    public PostgresSyncScheduler(CallRepository callRepository, JdbcTemplate jdbcTemplate) {
        this.callRepository = callRepository;
        this.jdbcTemplate = jdbcTemplate;
    }

    @Scheduled(fixedRateString = "${sync.cron-interval:600000}")
    public void syncCompletedCallsToPostgres() {
        List<CallSession> unsyncedCalls = callRepository
                .findByStatusAndSyncedToPostgresFalse(CallStatus.COMPLETED);

        if (unsyncedCalls.isEmpty()) {
            log.debug("No new completed calls to sync to PostgreSQL");
            return;
        }

        log.info("Syncing {} completed calls to PostgreSQL", unsyncedCalls.size());

        int successCount = 0;
        for (CallSession call : unsyncedCalls) {
            try {
                jdbcTemplate.update(
                    """
                    INSERT INTO call_sessions (id, agent_id, agent_name, call_started, call_ended,
                        duration_seconds, hangup_reason, agent_rating, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET
                        call_ended = EXCLUDED.call_ended,
                        duration_seconds = EXCLUDED.duration_seconds,
                        hangup_reason = EXCLUDED.hangup_reason,
                        agent_rating = EXCLUDED.agent_rating,
                        status = EXCLUDED.status
                    """,
                    call.getId(),
                    call.getAgentId(),
                    call.getAgentName(),
                    call.getCallStarted() != null ? Timestamp.from(call.getCallStarted()) : null,
                    call.getCallEnded() != null ? Timestamp.from(call.getCallEnded()) : null,
                    call.getDurationSeconds(),
                    call.getHangupReason() != null ? call.getHangupReason().getDisplayName() : null,
                    call.getAgentRating(),
                    call.getStatus().name()
                );

                // Mark as synced in MongoDB
                call.setSyncedToPostgres(true);
                callRepository.save(call);
                successCount++;
            } catch (Exception e) {
                log.error("Failed to sync call {} to PostgreSQL: {}", call.getId(), e.getMessage());
            }
        }

        log.info("Successfully synced {}/{} calls to PostgreSQL", successCount, unsyncedCalls.size());
    }
}
