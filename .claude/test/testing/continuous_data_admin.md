# Test Prompts: continuous_data_admin

> `DCT_TOOLSET=continuous_data_admin`

Start the server with this toolset, connect Claude Desktop, then run the prompts top to bottom in the same conversation thread. Prompts are chained — IDs discovered in earlier steps carry forward automatically.

For confirmation-flow prompts, the first call returns `confirmation_required`. Follow up with "yes, go ahead and confirm" to execute.

---

**data_tool — VDB operations**
1. List all VDBs
2. Search for VDBs with status enabled
3. Get the details of the first VDB from the previous result
4. Update the description of that VDB to "test update"
5. Get the defaults for provisioning a VDB by timestamp
6. Provision a new VDB by timestamp from the first dSource using those defaults, named test-cda-vdb-ts
7. Get the defaults for provisioning a VDB by snapshot
8. Provision a new VDB by snapshot from the first available snapshot, named test-cda-vdb-snap
9. Get the defaults for provisioning a VDB from a bookmark
10. Provision a new VDB from the first bookmark, named test-cda-vdb-bm
11. Get the defaults for provisioning a VDB by location
12. Provision a new VDB by location from the first dSource, named test-cda-vdb-loc
13. Provision an empty VDB using the first available environment and repository
14. Start test-cda-vdb-ts
15. Stop test-cda-vdb-ts
16. Enable test-cda-vdb-ts
17. Disable test-cda-vdb-ts
18. Refresh test-cda-vdb-ts by timestamp to one hour ago
19. Refresh test-cda-vdb-ts by snapshot using the most recent snapshot
20. Refresh test-cda-vdb-ts from the first bookmark
21. Refresh test-cda-vdb-ts by location
22. Undo the last refresh on test-cda-vdb-ts
23. Roll back test-cda-vdb-ts by timestamp to two hours ago
24. Roll back test-cda-vdb-ts by snapshot
25. Roll back test-cda-vdb-ts from the first bookmark
26. Switch the timeflow for test-cda-vdb-ts to the first available timeflow
27. Lock test-cda-vdb-ts
28. Unlock test-cda-vdb-ts
29. Get the compatible repositories for migrating test-cda-vdb-ts
30. Migrate test-cda-vdb-ts to the first compatible repository
31. Get the upgrade-compatible repositories for test-cda-vdb-ts
32. Upgrade test-cda-vdb-ts to the latest compatible repository (first call returns confirmation; confirm to proceed)
33. List all snapshots for test-cda-vdb-ts
34. Take a new snapshot of test-cda-vdb-ts
35. List all bookmarks for test-cda-vdb-ts
36. Search for bookmarks on test-cda-vdb-ts
37. Get the deletion dependencies for test-cda-vdb-ts
38. Verify the JDBC connection for test-cda-vdb-ts
39. Get the tags for test-cda-vdb-ts
40. Add the tag provisioned=true to test-cda-vdb-ts
41. Remove the provisioned=true tag from test-cda-vdb-ts
42. Export test-cda-vdb-ts in-place
43. Export test-cda-vdb-ts in-place using ASM
44. Export test-cda-vdb-ts by snapshot
45. Export test-cda-vdb-ts by timestamp
46. Export test-cda-vdb-ts by location
47. Export test-cda-vdb-ts from the first bookmark
48. Export test-cda-vdb-ts to ASM by snapshot
49. Export test-cda-vdb-ts to ASM by timestamp
50. Export test-cda-vdb-ts to ASM by location
51. Export test-cda-vdb-ts to ASM from the first bookmark
52. Clean up the last export for test-cda-vdb-ts
53. Finalize the last export for test-cda-vdb-ts
54. Delete test-cda-vdb-ts (first call returns confirmation; confirm to proceed)

**data_tool — VDB Group operations**
55. List all VDB groups
56. Search for all VDB groups
57. Get the details of the first VDB group from the previous result
58. Create a new VDB group named test-cda-group with the first two available VDBs
59. Update the description of test-cda-group to "test group"
60. Refresh test-cda-group
61. Refresh test-cda-group from the first bookmark
62. Refresh test-cda-group by snapshot
63. Refresh test-cda-group by timestamp to one hour ago
64. Roll back test-cda-group
65. Lock test-cda-group
66. Unlock test-cda-group
67. Start test-cda-group
68. Stop test-cda-group
69. Enable test-cda-group
70. Disable test-cda-group
71. Get the latest snapshots for test-cda-group
72. Get the timestamp summary for test-cda-group
73. List the bookmarks for test-cda-group
74. Search for bookmarks in test-cda-group
75. Get the tags for test-cda-group
76. Add the tag group=cda to test-cda-group
77. Remove the group=cda tag from test-cda-group
78. Provision a new VDB group from the first bookmark, named test-cda-group-provisioned
79. Delete test-cda-group (first call returns confirmation; confirm to proceed)

**data_tool — dSource operations**
80. List all dSources
81. Search for all dSources
82. Get the details of the first dSource from the previous result
83. Enable that dSource
84. Disable that dSource
85. List all snapshots for that dSource
86. Take a new snapshot of that dSource
87. Get the upgrade-compatible repositories for that dSource
88. Upgrade that dSource to the latest compatible repository (first call returns confirmation; confirm to proceed)
89. Get the deletion dependencies for that dSource
90. Get the tags for that dSource
91. Add the tag source=primary to that dSource
92. Remove the source=primary tag from that dSource
93. Get the Oracle dSource link defaults
94. Link an Oracle dSource using those defaults with a test source name
95. Get the Oracle staging-push dSource link defaults
96. Link an Oracle staging-push dSource using those defaults
97. Update the Oracle dSource configuration
98. Attach a source to that Oracle dSource
99. Detach the source from that Oracle dSource
100. Upgrade that Oracle dSource (first call returns confirmation; confirm to proceed)
101. Get the ASE dSource link defaults
102. Link an ASE dSource using those defaults
103. Update the ASE dSource configuration
104. Get the AppData dSource link defaults
105. Link an AppData dSource using those defaults
106. Update the AppData dSource configuration
107. Get the MSSQL dSource link defaults
108. Link an MSSQL dSource using those defaults
109. Get the MSSQL staging-push dSource link defaults
110. Link an MSSQL staging-push dSource using those defaults
111. Attach a source to that MSSQL staging-push dSource
112. Update the MSSQL dSource configuration
113. Attach a source to the MSSQL dSource
114. Detach the source from the MSSQL dSource
115. Export the first dSource by snapshot
116. Export the first dSource by timestamp
117. Export the first dSource by location
118. Export the first dSource from the first bookmark
119. Export the first dSource to ASM by snapshot
120. Export the first dSource to ASM by timestamp
121. Export the first dSource to ASM by location
122. Export the first dSource to ASM from the first bookmark
123. Delete the first dSource (first call returns confirmation; confirm to proceed)

**snapshot_bookmark_tool — Snapshot operations**
124. Search for all snapshots
125. Get the details of the first snapshot from the previous result
126. Update the retention of that snapshot to 30 days
127. Get the timeflow range for that snapshot
128. Get the runtime details for that snapshot
129. Find a snapshot by location using the first snapshot's location value
130. Find a snapshot by timestamp one hour ago
131. Get the tags for that snapshot
132. Add the tag retain=true to that snapshot
133. Remove the retain=true tag from that snapshot
134. Unset the expiration on that snapshot
135. Delete that snapshot (first call returns confirmation; confirm to proceed)

**snapshot_bookmark_tool — Bookmark operations**
136. Search for all bookmarks
137. Get the details of the first bookmark from the previous result
138. Create a new bookmark named test-cda-bookmark on the first VDB
139. Update that bookmark's name to test-cda-bookmark-updated
140. Get the VDB groups associated with that bookmark
141. Get the tags for that bookmark
142. Add the tag shared=true to that bookmark
143. Remove the shared=true tag from that bookmark
144. Delete that bookmark (first call returns confirmation; confirm to proceed)

**instance_tool — CDB operations**
145. Search for all CDBs
146. Get the details of the first CDB from the previous result
147. Update that CDB's configuration
148. Enable that CDB
149. Disable that CDB
150. Get the tags for that CDB
151. Add the tag db=cdb to that CDB
152. Remove the db=cdb tag from that CDB
153. Delete that CDB (first call returns confirmation; confirm to proceed)

**instance_tool — vCDB operations**
154. Search for all vCDBs
155. Get the details of the first vCDB from the previous result
156. Update that vCDB's configuration
157. Enable that vCDB
158. Disable that vCDB
159. Start that vCDB
160. Stop that vCDB
161. Get the tags for that vCDB
162. Add the tag db=vcdb to that vCDB
163. Remove the db=vcdb tag from that vCDB
164. Delete that vCDB (first call returns confirmation; confirm to proceed)

**database_template_tool**
165. Search for all database templates
166. Get the details of the first database template
167. Create a new database template named test-cda-template
168. Update test-cda-template to rename it to test-cda-template-updated
169. Get the tags for test-cda-template-updated
170. Add the tag type=mssql to test-cda-template-updated
171. Remove the type=mssql tag from test-cda-template-updated
172. Delete test-cda-template-updated (first call returns confirmation; confirm to proceed)

**hook_template_tool**
173. Search for all hook templates
174. Get the details of the first hook template
175. Create a new hook template named test-cda-hook
176. Update test-cda-hook to rename it to test-cda-hook-updated
177. Get the tags for test-cda-hook-updated
178. Add the tag stage=pre to test-cda-hook-updated
179. Remove the stage=pre tag from test-cda-hook-updated
180. Delete test-cda-hook-updated (first call returns confirmation; confirm to proceed)

**virtualization_policy_tool**
181. Search for all virtualization policies
182. Get the details of the first policy
183. Create a new retention policy named test-cda-policy with 7-day retention
184. Update test-cda-policy retention to 14 days
185. Search for the targets of test-cda-policy
186. Apply test-cda-policy to the first VDB
187. Unapply test-cda-policy from the first VDB
188. Get the tags for test-cda-policy
189. Add the tag scope=global to test-cda-policy
190. Remove the scope=global tag from test-cda-policy
191. Delete test-cda-policy (first call returns confirmation; confirm to proceed)

**job_tool**
192. Search for all jobs
193. Get the details of the first job
194. Get the result of the first completed job
195. Abandon the first running job, if any exist (first call returns confirmation; confirm to proceed)
196. Get the tags for the first job
197. Add the tag monitored=true to the first job
198. Remove the monitored=true tag from the first job

**engine_tool**
199. Search for all registered engines
200. Get the details of the first engine from the previous result
201. Update that engine's description to "test engine"
202. Get the auto-tagging configuration for that engine
203. Get the compliance application settings for that engine
204. Search the compliance application settings for that engine
205. Get the tags for that engine
206. Add the tag region=us-east to that engine
207. Remove the region=us-east tag from that engine
208. Register a new engine using a test engine address (first call returns confirmation; confirm to proceed)
209. Unregister the test engine (first call returns confirmation; confirm to proceed)

**environment_source_tool — Environment operations**
210. Search for all environments
211. Get the details of the first environment
212. Create a new environment using a test host address
213. Update that environment's description to "test env"
214. Enable that environment
215. Disable that environment
216. Refresh that environment
217. List the hosts in that environment
218. Get the details of the first host in that environment
219. Update that host's configuration
220. Delete that host (first call returns confirmation; confirm to proceed)
221. List the listeners in that environment
222. Get the tags for that environment
223. Add the tag location=datacenter-1 to that environment
224. Remove the location=datacenter-1 tag from that environment
225. Get the compatible repositories by snapshot for that environment
226. Get the compatible repositories by timestamp for that environment
227. Get the compatible repositories by location for that environment
228. Update the first repository in that environment
229. Delete that repository (first call returns confirmation; confirm to proceed)
230. Add users to that environment
231. Set the primary user for that environment
232. Update that environment's user
233. Delete that environment's user
234. Delete that environment (first call returns confirmation; confirm to proceed)

**environment_source_tool — Source operations**
235. Search for all sources
236. List all sources
237. Get the details of the first source
238. Verify the JDBC connection for that source
239. Get the staging-compatible repositories for that source
240. Get the tags for that source
241. Add the tag monitored=true to that source
242. Remove the monitored=true tag from that source
243. Create an Oracle source configuration
244. Update that Oracle source configuration
245. Create a Postgres source configuration
246. Update that Postgres source configuration
247. Create an ASE source configuration
248. Update that ASE source configuration
249. Create an AppData source configuration
250. Update that AppData source configuration
251. Delete the first source (first call returns confirmation; confirm to proceed)

**replication_tool — Replication Profile operations**
252. Search for all replication profiles
253. Get the details of the first replication profile
254. Create a new replication profile named test-cda-replication-profile
255. Update that profile's description to "cda replication test"
256. Execute that replication profile (first call returns confirmation; confirm to proceed)
257. Enable tag replication for that profile
258. Disable tag replication for that profile
259. Get the tags for that profile
260. Add the tag target=dr-site to that profile
261. Remove the target=dr-site tag from that profile
262. Delete that profile (first call returns confirmation; confirm to proceed)

**replication_tool — Namespace operations**
263. List all namespaces
264. Search for all namespaces
265. Get the details of the first namespace
266. Update that namespace's description
267. Failover the first namespace (first call returns confirmation; confirm to proceed)
268. Commit the failover for that namespace (first call returns confirmation; confirm to proceed)
269. Fail back that namespace (first call returns confirmation; confirm to proceed)
270. Discard that namespace (first call returns confirmation; confirm to proceed)
271. Delete that namespace (first call returns confirmation; confirm to proceed)

**replication_tool — Held Space operations**
272. Get the deletion dependencies for the first held space
273. Delete the first held space (first call returns confirmation; confirm to proceed)

**reporting_tool**
274. Search the storage savings report
275. Get the storage capacity report
276. Get the virtualization storage summary report
277. Get the VDB inventory report
278. Search the VDB inventory report filtered by engine
279. Get the dSource consumption report
280. Get the engine performance analytics report
281. Get the dataset performance analytics report
282. Get the API usage report
283. Get the audit logs summary report
284. Get the license information
285. Get the virtualization jobs history
286. Search the virtualization jobs history for the last 7 days
287. Get the virtualization actions history
288. Search the virtualization actions history for the last 7 days
289. Get the virtualization faults history
290. Search the virtualization faults history for the last 7 days
291. Resolve or ignore the first fault from the previous result
292. Resolve all faults for the first engine
293. Resolve the first fault by its ID
294. Get the virtualization alerts history
295. Search the virtualization alerts history for the last 7 days
296. Search for all scheduled reports
297. Get the details of the first scheduled report
298. Create a scheduled report for the storage savings report delivered weekly
299. Update that scheduled report to monthly delivery
300. Delete that scheduled report (first call returns confirmation; confirm to proceed)

**iam_tool — Account operations**
301. Search for all accounts
302. Get the details of the first account
303. Create a new account with username test-cda-user
304. Update test-cda-user's first name to Test
305. Enable the test-cda-user account
306. Disable the test-cda-user account
307. Reset the password for test-cda-user
308. Get the tags for test-cda-user
309. Add the tag team=platform to test-cda-user
310. Remove the team=platform tag from test-cda-user
311. Get the UI profiles for test-cda-user
312. Get the current password policies
313. Update the password policy minimum length to 12

**iam_tool — Role operations**
314. Search for all roles
315. Get the details of the first role
316. Create a new role named test-cda-role
317. Update test-cda-role's description
318. Add permissions to test-cda-role
319. Remove those permissions from test-cda-role
320. Get the tags for test-cda-role
321. Add the tag scope=limited to test-cda-role
322. Remove the scope=limited tag from test-cda-role
323. Add UI profiles to test-cda-role
324. Remove those UI profiles from test-cda-role
325. Delete test-cda-role (first call returns confirmation; confirm to proceed)

**iam_tool — Access Group operations**
326. Search for all access groups
327. Get the details of the first access group
328. Create a new access group named test-cda-access-group
329. Update that access group's description
330. Add a scope to test-cda-access-group
331. Get the first scope of that access group
332. Update that scope
333. Add object tags to that scope
334. Remove those object tags from that scope
335. Add objects to that scope
336. Remove those objects from that scope
337. Add always-allowed permissions to that scope
338. Remove those always-allowed permissions from that scope
339. Delete that scope
340. Get the tags for test-cda-access-group
341. Add the tag owner=admin to test-cda-access-group
342. Remove the owner=admin tag from test-cda-access-group
343. Delete test-cda-access-group (first call returns confirmation; confirm to proceed)
344. Delete test-cda-user (first call returns confirmation; confirm to proceed)

**iam_tool — API Client operations**
345. List all API clients
346. Create a new API client named test-cda-api-client
347. Delete test-cda-api-client (first call returns confirmation; confirm to proceed)

**toolkit_tool**
348. Search for all toolkits
349. Get the details of the first toolkit from the previous result
350. Upload a new toolkit using a local test toolkit file
351. Get the tags for the first toolkit
352. Add the tag version=1.0 to the first toolkit
353. Remove the version=1.0 tag from the first toolkit
354. Delete that toolkit (first call returns confirmation; confirm to proceed)

**data_connection_tool**
355. Search for all data connections
356. Get the details of the first data connection
357. Update that data connection's configuration
358. Get the tags for that data connection
359. Add the tag env=prod to that data connection
360. Remove the env=prod tag from that data connection

**tag_tool**
361. Search for all tags
362. Get the details of the first tag
363. Create a new tag with key tier and value gold
364. Get the usages of the tier=gold tag
365. Search the usages of the tier=gold tag
366. Delete the tier=gold tag (first call returns confirmation; confirm to proceed)

**staging_source_tool**
367. List all staging sources
368. Search for all staging sources
369. Get the details of the first staging source
370. Update that staging source's configuration
371. Get the tags for the first staging source
372. Add the tag monitored=true to that staging source
373. Remove the monitored=true tag from that staging source

**staging_cdb_tool**
374. List all staging CDBs
375. Search for all staging CDBs
376. Get the details of the first staging CDB
377. Update that staging CDB's configuration
378. Enable that staging CDB
379. Disable that staging CDB
380. Upgrade that staging CDB (first call returns confirmation; confirm to proceed)
381. Get the tags for that staging CDB
382. Add the tag version=19c to that staging CDB
383. Remove the version=19c tag from that staging CDB
384. Delete that staging CDB (first call returns confirmation; confirm to proceed)

**cdb_dsource_tool**
385. List all CDB dSources
386. Search for all CDB dSources
387. Get the details of the first CDB dSource
388. Attach a CDB to that CDB dSource
389. Detach the CDB from that CDB dSource
390. Enable that CDB dSource
391. Disable that CDB dSource
392. Upgrade that CDB dSource (first call returns confirmation; confirm to proceed)
393. Delete that CDB dSource (first call returns confirmation; confirm to proceed)

**group_tool**
394. List all dataset groups
395. Search for all dataset groups
396. Get the details of the first dataset group

**timeflow_tool**
397. List all timeflows
398. Search for all timeflows
399. Get the details of the first timeflow
400. Update that timeflow's name to test-cda-timeflow
401. Get the snapshot day range for that timeflow
402. Repair that timeflow
403. Get the tags for that timeflow
404. Add the tag source=prod to that timeflow
405. Remove the source=prod tag from that timeflow
406. Delete that timeflow (first call returns confirmation; confirm to proceed)

**vault_tool — Hashicorp Vault operations**
407. List all Hashicorp vaults
408. Search for all Hashicorp vaults
409. Get the details of the first Hashicorp vault
410. Create a new Hashicorp vault named test-cda-vault
411. Get the tags for test-cda-vault
412. Add the tag managed=true to test-cda-vault
413. Remove the managed=true tag from test-cda-vault
414. Delete test-cda-vault (first call returns confirmation; confirm to proceed)

**vault_tool — Kerberos Config operations**
415. List all Kerberos configurations
416. Search for all Kerberos configurations
417. Get the details of the first Kerberos configuration

**diagnostic_tool**
418. Check engine connectivity for the first engine
419. Check database connectivity for the first data connection
420. Check NetBackup connectivity
421. Check Commvault connectivity
422. Run a network latency test to the first engine
423. Get the network latency test result for the previous job
424. Run a DSP network test to the first engine
425. Get the DSP network test result
426. Run a network throughput test to the first engine
427. Get the network throughput test result
428. Validate file mapping by snapshot for the first VDB
429. Validate file mapping by location for the first VDB
430. Validate file mapping by timestamp for the first VDB
431. Validate file mapping from bookmark for the first VDB
