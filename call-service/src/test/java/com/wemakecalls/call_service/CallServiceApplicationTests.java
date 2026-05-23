package com.wemakecalls.call_service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
@EnabledIf("isMongoAvailable")
class CallServiceApplicationTests {

	@Test
	void contextLoads() {
	}

	static boolean isMongoAvailable() {
		try (var socket = new java.net.Socket()) {
			socket.connect(new java.net.InetSocketAddress("localhost", 27017), 500);
			return true;
		} catch (Exception e) {
			return false;
		}
	}

}
