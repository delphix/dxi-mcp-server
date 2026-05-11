# Test Prompts: platform_admin

> `DCT_TOOLSET=platform_admin`

Start the server with this toolset, connect Claude Desktop, then run the prompts top to bottom in the same conversation thread. Prompts are chained — IDs discovered in earlier steps carry forward automatically.

For confirmation-flow prompts, the first call returns `confirmation_required`. Follow up with "yes, go ahead and confirm" to execute.

---

**job_tool**
1. Search for all jobs
2. Get the details of the first job
3. Get the result of the first completed job
4. Abandon the first running job, if any exist (first call returns confirmation; confirm to proceed)
5. Get the tags for the first job
6. Add the tag monitored=true to the first job
7. Remove the monitored=true tag from the first job

**engine_tool**
8. Search for all registered engines
9. Get the details of the first engine
10. Register a new engine using a test engine address (first call returns confirmation; confirm to proceed)
11. Update that engine's description to "managed by platform admin"
12. Get the tags for that engine
13. Add the tag tier=production to that engine
14. Remove the tier=production tag from that engine
15. Unregister the test engine (first call returns confirmation; confirm to proceed)

**environment_tool**
16. Search for all environments
17. Get the details of the first environment
18. Create a new environment using a test host address
19. Update that environment's description to "platform admin test env"
20. Add users to that environment
21. Set the primary user for that environment
22. Update that environment's user
23. Delete that environment's user
24. Enable that environment
25. Disable that environment
26. Refresh that environment
27. List the hosts in that environment
28. List the listeners in that environment
29. Get the tags for that environment
30. Add the tag managed=true to that environment
31. Remove the managed=true tag from that environment
32. Delete that environment (first call returns confirmation; confirm to proceed)

**source_tool**
33. Search for all sources
34. Get the details of the first source
35. Update that source's configuration
36. Get the tags for that source
37. Add the tag monitored=true to that source
38. Remove the monitored=true tag from that source

**replication_tool — Replication Profile operations**
39. Search for all replication profiles
40. Get the details of the first replication profile
41. Create a new replication profile named test-pa-replication-profile
42. Update that profile's description to "platform admin test"
43. Execute that replication profile (first call returns confirmation; confirm to proceed)
44. Enable tag replication for that profile
45. Disable tag replication for that profile
46. Get the tags for that profile
47. Add the tag managed=dr to that profile
48. Remove the managed=dr tag from that profile
49. Delete that profile (first call returns confirmation; confirm to proceed)

**replication_tool — Namespace operations**
50. List all namespaces
51. Search for all namespaces
52. Get the details of the first namespace
53. Update that namespace's description
54. Failover the first namespace (first call returns confirmation; confirm to proceed)
55. Commit the failover for that namespace (first call returns confirmation; confirm to proceed)
56. Fail back that namespace (first call returns confirmation; confirm to proceed)
57. Discard that namespace (first call returns confirmation; confirm to proceed)
58. Delete that namespace (first call returns confirmation; confirm to proceed)

**replication_tool — Held Space operations**
59. Get the deletion dependencies for the first held space
60. Delete the first held space (first call returns confirmation; confirm to proceed)

**reporting_tool**
61. Search the storage savings report
62. Get the storage capacity report
63. Get the virtualization storage summary report
64. Get the VDB inventory report
65. Search the VDB inventory report filtered by engine
66. Get the dSource consumption report
67. Get the engine performance analytics report
68. Get the dataset performance analytics report
69. Get the API usage report
70. Get the audit logs summary report
71. Get the license information
72. Change the license (first call returns confirmation; confirm to proceed)
73. Get the virtualization jobs history
74. Search the virtualization jobs history for the last 7 days
75. Get the virtualization actions history
76. Search the virtualization actions history for the last 7 days
77. Get the virtualization faults history
78. Search the virtualization faults history for the last 7 days
79. Resolve or ignore the first fault from the previous result
80. Resolve all faults for the first engine
81. Resolve the first fault by its ID
82. Get the virtualization alerts history
83. Search the virtualization alerts history for the last 7 days
84. Search for all scheduled reports
85. Get the details of the first scheduled report
86. Create a scheduled report for the VDB inventory delivered weekly
87. Update that scheduled report to monthly delivery
88. Delete that scheduled report (first call returns confirmation; confirm to proceed)

**iam_tool — Account operations**
89. Search for all accounts
90. Get the details of the first account
91. Create a new account with username test-pa-user
92. Update test-pa-user's last name to Admin
93. Enable the test-pa-user account
94. Disable the test-pa-user account
95. Reset the password for test-pa-user
96. Get the tags for test-pa-user
97. Add the tag role=admin to test-pa-user
98. Remove the role=admin tag from test-pa-user
99. Get the UI profiles for test-pa-user
100. Get the current password policies
101. Update the password policy minimum length to 14

**iam_tool — Role operations**
102. Search for all roles
103. Get the details of the first role
104. Create a new role named test-pa-role
105. Update test-pa-role's description
106. Add permissions to test-pa-role
107. Remove those permissions from test-pa-role
108. Get the tags for test-pa-role
109. Add the tag level=elevated to test-pa-role
110. Remove the level=elevated tag from test-pa-role
111. Add UI profiles to test-pa-role
112. Remove those UI profiles from test-pa-role
113. Delete test-pa-role (first call returns confirmation; confirm to proceed)

**iam_tool — Access Group operations**
114. Search for all access groups
115. Get the details of the first access group
116. Create a new access group named test-pa-access-group
117. Update that access group's description to "platform admin test group"
118. Add a scope to test-pa-access-group
119. Get the first scope of that access group
120. Update that scope
121. Add object tags to that scope
122. Remove those object tags from that scope
123. Add objects to that scope
124. Remove those objects from that scope
125. Add always-allowed permissions to that scope
126. Remove those always-allowed permissions from that scope
127. Delete that scope
128. Get the tags for test-pa-access-group
129. Add the tag managed=true to test-pa-access-group
130. Remove the managed=true tag from test-pa-access-group
131. Delete test-pa-access-group (first call returns confirmation; confirm to proceed)
132. Delete test-pa-user (first call returns confirmation; confirm to proceed)

**iam_tool — API Client operations**
133. List all API clients
134. Create a new API client named test-pa-api-client
135. Delete test-pa-api-client (first call returns confirmation; confirm to proceed)

**data_connection_tool**
136. Search for all data connections
137. Get the details of the first data connection
138. Update that data connection's configuration
139. Get the tags for that data connection
140. Add the tag tier=gold to that data connection
141. Remove the tier=gold tag from that data connection

**tag_tool**
142. Search for all tags
143. Get the details of the first tag
144. Create a new tag with key classification and value internal
145. Get the usages of the classification=internal tag
146. Search the usages of the classification=internal tag
147. Delete the classification=internal tag (first call returns confirmation; confirm to proceed)

**toolkit_tool**
148. Search for all toolkits
149. Get the details of the first toolkit
150. Upload a new toolkit using a local test toolkit file
151. Get the tags for the first toolkit
152. Add the tag release=stable to that toolkit
153. Remove the release=stable tag from that toolkit
154. Delete that toolkit (first call returns confirmation; confirm to proceed)

**admin_platform_tool — AI Services**
155. List all available LLM models
156. Get the details of the first LLM model
157. Get the current AI gateway configuration
158. Update the AI gateway configuration
159. Enable AI services

**admin_platform_tool — Telemetry & Properties**
160. Get the current DCT properties
161. Update the DCT properties
162. Get the current telemetry configuration
163. Update the telemetry configuration

**admin_platform_tool — SMTP Configuration**
164. Get the current SMTP configuration
165. Update the SMTP configuration with a test SMTP server address
166. Validate the SMTP configuration

**admin_platform_tool — LDAP Configuration**
167. Get the current LDAP configuration
168. Update the LDAP configuration
169. Validate the LDAP configuration

**admin_platform_tool — SAML Configuration**
170. Get the current SAML configuration
171. Update the SAML configuration

**admin_platform_tool — Proxy Configuration**
172. Get the current proxy configuration
173. Update the proxy configuration

**vault_tool — Hashicorp Vault operations**
174. List all Hashicorp vaults
175. Search for all Hashicorp vaults
176. Get the details of the first Hashicorp vault
177. Create a new Hashicorp vault named test-pa-vault
178. Get the tags for test-pa-vault
179. Add the tag managed=true to test-pa-vault
180. Remove the managed=true tag from test-pa-vault
181. Delete test-pa-vault (first call returns confirmation; confirm to proceed)

**vault_tool — Kerberos Config operations**
182. List all Kerberos configurations
183. Search for all Kerberos configurations
184. Get the details of the first Kerberos configuration

**diagnostic_tool**
185. Check engine connectivity for the first engine
186. Check database connectivity for the first data connection
187. Check NetBackup connectivity
188. Check Commvault connectivity
189. Run a network latency test to the first engine
190. Get the network latency test result for the previous job
191. Run a DSP network test to the first engine
192. Get the DSP network test result
193. Run a network throughput test to the first engine
194. Get the network throughput test result
195. Validate file mapping by snapshot for the first VDB
196. Validate file mapping by location for the first VDB
197. Validate file mapping by timestamp for the first VDB
198. Validate file mapping from bookmark for the first VDB
