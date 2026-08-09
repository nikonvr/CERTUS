# CERTUS-ExceptionHandlingGuidelines

This document summarizes the best practices to follow when handling exceptions within the CERTUS application, in order to avoid technical debt, facilitate debugging and make the error reporting system more reliable.

---

## 1. Ban empty`except:`clauses (Bare Excepts)

Using`except:`withoutanexceptiontypecatchesabsolutelyallerrors,includingimportantsysteminterruptslike`SystemExit`,`KeyboardInterrupt`ormemoryerrorslike`MemoryError`.

* **To avoid:**
  ```python
  try:
      traitement()
  except:
      pass
  ```
* **Recommended:**Specifyatleast`Exception`ifyouwishtocatchallstandardapplicationerrors:
  ```python
  try:
      traitement()
  exceptExceptionase:
logging.error("processing failure: %s", e)
  ```

---

## 2. Avoid Smothering Exceptions (Silent Passes)

Runningasilent`pass`preventsidentifyingtherootofabuginproduction.Anycaughtexceptionthatisnotreissuedmustbedocumentedandloggedatanappropriatelevel(`debug`,`warning`or`error`).

* **To avoid:**
  ```python
  try:
      charger_config()
  except OSError:
      pass
  ```
* **Recommended :**
  ```python
  try:
      charger_config()
  except OSError as e:
      logging.warning("Impossible de charger la configuration, utilisation des values par defaut: %s", e)
  ```
* **Exceptionallowed:**Ifsilentbehaviorislegitimatelyandnominallyrequired,documentitexplicitlyinthecodewitha`#Explanation`comment.

---

## 3. Prefer specific exceptions to generics

Youshouldonlycapturethetypesoferrorsthattheblockisdesignedtohandle.Forexample,ifyouexpectakeymissingerrorinadictionary,catch`KeyError`ratherthan`Exception`.

* **Example :**
  ```python
  try:
      value = data["key"]
  except KeyError:
      value = DEFAULT_VAL
  ```

---

## 4. Preserve the stack trace

Whenhandlingcriticalerrors,itiscrucialtokeeptheerrorhistoryinthelogswiththe`exc_info=True`parameterorbyusing`logging.exception`.

* **Recommended :**
  ```python
  try:
      operation_complexe()
  exceptException:
      logging.exception("L'operation complexe a echoue")
  ```
