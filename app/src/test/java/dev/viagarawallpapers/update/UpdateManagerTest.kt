// SPDX-License-Identifier: GPL-3.0-or-later
package dev.viagarawallpapers.update

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateManagerTest {

    @Test
    fun `isVersionGreater recognizes newer beta version over older stable`() {
        assertTrue(UpdateManager.isVersionGreater("1.0.2-beta", "1.0.0"))
        assertTrue(UpdateManager.isVersionGreater("v1.0.2-beta", "1.0.1"))
        assertTrue(UpdateManager.isVersionGreater("1.0.2-beta", "v1.0.1"))
        assertTrue(UpdateManager.isVersionGreater("1.0.3-beta", "1.0.2"))
    }

    @Test
    fun `isVersionGreater recognizes stable version is newer than pre-release of same version`() {
        assertTrue(UpdateManager.isVersionGreater("1.0.0", "1.0.0-beta"))
        assertTrue(UpdateManager.isVersionGreater("v1.0.0", "1.0.0-beta"))
    }

    @Test
    fun `isVersionGreater returns false when remote beta is compared against same stable`() {
        assertFalse(UpdateManager.isVersionGreater("1.0.0-beta", "1.0.0"))
    }

    @Test
    fun `isVersionGreater compares identical versions as not greater`() {
        assertFalse(UpdateManager.isVersionGreater("1.0.0", "1.0.0"))
        assertFalse(UpdateManager.isVersionGreater("1.0.0-beta", "1.0.0-beta"))
        assertFalse(UpdateManager.isVersionGreater("v1.0.0-beta", "1.0.0-beta"))
    }

    @Test
    fun `isVersionGreater compares pre-release revisions correctly`() {
        assertTrue(UpdateManager.isVersionGreater("1.0.0-beta2", "1.0.0-beta1"))
        assertTrue(UpdateManager.isVersionGreater("1.0.0-beta.2", "1.0.0-beta.1"))
        assertFalse(UpdateManager.isVersionGreater("1.0.0-beta1", "1.0.0-beta2"))
    }

    @Test
    fun `isVersionGreater handles patch and minor revisions correctly`() {
        assertTrue(UpdateManager.isVersionGreater("1.1.0", "1.0.0"))
        assertTrue(UpdateManager.isVersionGreater("2.0.0", "1.99.99"))
        assertFalse(UpdateManager.isVersionGreater("1.0.0", "1.1.0"))
    }
}
